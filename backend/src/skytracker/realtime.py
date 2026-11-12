"""Single WebSocket channel (/ws) with topic subscriptions.

Messages are JSON objects with a "type" field:
  client -> server: {"type": "ping"} | {"type": "subscribe", "topic": "job:<id>"}
                    | {"type": "unsubscribe", ...}
  server -> client: {"type": "hello"} | {"type": "pong"} | {"type": "progress", ...}
                    | {"type": "assistant_chunk", ...} | {"type": "admin_event", ...}
                    | {"type": "error", "code": ...}
Everything sent over WS is also reachable over HTTP, so the WS is an enhancement, never a requirement.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections import defaultdict
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .security import SESSION_COOKIE
from .settings import get_settings

router = APIRouter()

TOPIC_RE = re.compile(r"^(job:[A-Za-z0-9_-]{6,64}|admin)$")
MAX_MSG_BYTES = 4096
MAX_TOPICS_PER_CONN = 20


class ConnectionManager:
    def __init__(self) -> None:
        self._topics: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, ws: WebSocket, topic: str) -> None:
        async with self._lock:
            self._topics[topic].add(ws)

    async def unsubscribe(self, ws: WebSocket, topic: str | None = None) -> None:
        async with self._lock:
            topics = [topic] if topic else list(self._topics)
            for t in topics:
                self._topics.get(t, set()).discard(ws)
                if t in self._topics and not self._topics[t]:
                    del self._topics[t]

    async def publish(self, topic: str, message: dict) -> int:
        async with self._lock:
            targets = list(self._topics.get(topic, ()))
        sent = 0
        for ws in targets:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:  # noqa: BLE001 - dead socket; cleaned up on disconnect
                await self.unsubscribe(ws)
        return sent

    def topic_count(self) -> int:
        return len(self._topics)


manager = ConnectionManager()


def _origin_allowed(origin: str | None) -> bool:
    s = get_settings()
    if not s.is_production:
        return True
    if not origin:
        return False
    allowed = {urlparse(s.public_base_url).netloc} | {urlparse(o).netloc for o in s.origins}
    return urlparse(origin).netloc in allowed


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    if not _origin_allowed(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    sid = ws.cookies.get(SESSION_COOKIE)
    await ws.send_json({"type": "hello", "anonymous": True, "has_session": bool(sid)})
    topics: set[str] = set()
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_MSG_BYTES:
                await ws.send_json({"type": "error", "code": "MESSAGE_TOO_LARGE"})
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "code": "BAD_JSON"})
                continue
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "ping":
                await ws.send_json({"type": "pong"})
            elif kind in ("subscribe", "unsubscribe"):
                topic = str(msg.get("topic", ""))
                # "admin" needs an authenticated admin session; accounts arrive in a later phase
                if not TOPIC_RE.match(topic) or topic == "admin":
                    await ws.send_json({"type": "error", "code": "FORBIDDEN_TOPIC", "topic": topic})
                    continue
                if kind == "subscribe":
                    if len(topics) >= MAX_TOPICS_PER_CONN:
                        await ws.send_json({"type": "error", "code": "TOO_MANY_TOPICS"})
                        continue
                    topics.add(topic)
                    await manager.subscribe(ws, topic)
                else:
                    topics.discard(topic)
                    await manager.unsubscribe(ws, topic)
                await ws.send_json({"type": kind + "d", "topic": topic})
            else:
                await ws.send_json({"type": "error", "code": "UNKNOWN_TYPE"})
    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(Exception):
            await manager.unsubscribe(ws)
