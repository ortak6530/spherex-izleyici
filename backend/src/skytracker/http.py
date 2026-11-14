"""Single outbound HTTP client.

- Only hosts in config/upstreams.toml are reachable (SSRF protection); every redirect hop is checked.
- Per-upstream-group concurrency limits (politeness towards IRSA/CDS/JPL).
- Retries on 429/502/503/504 honouring Retry-After (IRSA answers 503 "Server busy, retry later.").
- certifi CA bundle (the Windows store lacks the CDS chain; Linux images are fine either way).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from urllib.parse import urlparse

import certifi
import httpx

from . import __version__
from .config_loader import upstreams

log = logging.getLogger("skytracker.http")

USER_AGENT = f"SPHEREx-Gokyuzu-Izleyici/{__version__} (+NASA Space Apps 2026)"
RETRY_STATUS = {429, 502, 503, 504}


class UpstreamError(Exception):
    """Raised with a stable code the API turns into a JSON error."""

    def __init__(self, code: str, upstream: str, detail: str = ""):
        super().__init__(f"{code} {upstream} {detail}")
        self.code = code
        self.upstream = upstream


class HostNotAllowed(UpstreamError):
    def __init__(self, host: str):
        super().__init__("HOST_NOT_ALLOWED", host)


def _check_url(url: str | httpx.URL) -> str:
    host = (urlparse(str(url)).hostname or "").lower()
    if urlparse(str(url)).scheme != "https" or host not in upstreams().allowed_hosts:
        raise HostNotAllowed(host)
    return upstreams().group_for_host(host) or "default"


class Http:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._sems: dict[str, asyncio.Semaphore] = {}
        # Passive health per upstream group: the outcome of the server's own last request (no pings)
        self._health: dict[str, dict] = {}

    def _note(self, group: str, ok: bool, detail: str) -> None:
        self._health[group] = {
            "ok": ok,
            "detail": detail,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def health(self) -> dict[str, dict]:
        return dict(self._health)

    def client(self) -> httpx.AsyncClient:
        if self._client is None:

            async def _hook(request: httpx.Request) -> None:
                _check_url(request.url)  # also runs for each redirect hop

            self._client = httpx.AsyncClient(
                verify=certifi.where(),
                follow_redirects=True,
                max_redirects=3,
                headers={"User-Agent": USER_AGENT},
                event_hooks={"request": [_hook]},
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            )
        return self._client

    def _sem(self, group: str) -> asyncio.Semaphore:
        if group not in self._sems:
            g = upstreams().groups.get(group)
            self._sems[group] = asyncio.Semaphore(g.concurrency if g else 4)
        return self._sems[group]

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        json: dict | None = None,
        timeout: float | None = None,
        retries: int = 3,
    ) -> httpx.Response:
        group = _check_url(url)
        g = upstreams().groups.get(group)
        tmo = timeout or (g.timeout if g else 30)
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with self._sem(group):
                    resp = await self.client().request(
                        method,
                        url,
                        params=params,
                        headers=headers,
                        data=data,
                        files=files,
                        json=json,
                        timeout=tmo,
                    )
            except HostNotAllowed:
                raise
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                wait = min(2**attempt, 8) + random.random()  # noqa: S311 - jitter, not crypto
            else:
                if resp.status_code not in RETRY_STATUS or attempt == retries:
                    # 4xx is the request's fault (e.g. unknown name), not the service's
                    self._note(group, resp.status_code < 500, f"HTTP {resp.status_code}")
                    return resp
                ra = resp.headers.get("retry-after", "")
                wait = float(ra) if ra.replace(".", "", 1).isdigit() else min(2**attempt, 8)
                wait = min(wait, 15) + random.random()
                log.info("%s %s -> %s, retry in %.1fs", method, url[:90], resp.status_code, wait)
            if attempt < retries:
                await asyncio.sleep(wait)
        if isinstance(last_exc, httpx.TimeoutException):
            self._note(group, False, "timeout")
            raise UpstreamError("UPSTREAM_TIMEOUT", group, str(last_exc))
        self._note(group, False, "unreachable")
        raise UpstreamError("UPSTREAM_UNAVAILABLE", group, str(last_exc))

    async def get(self, url: str, **kw) -> httpx.Response:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw) -> httpx.Response:
        return await self.request("POST", url, **kw)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


http = Http()


def raise_for_upstream(resp: httpx.Response, upstream: str) -> None:
    if resp.status_code in RETRY_STATUS:
        raise UpstreamError("UPSTREAM_BUSY", upstream, str(resp.status_code))
    if resp.status_code >= 400:
        raise UpstreamError("UPSTREAM_UNAVAILABLE", upstream, str(resp.status_code))
