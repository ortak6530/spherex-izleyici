"""Slow queries: cached answers come at once, otherwise a job reports its steps (WS + HTTP fallback)."""

import asyncio
import time

import pytest

from skytracker.api.v1 import objects as O
from skytracker.http import UpstreamError


@pytest.fixture
def mem_cache(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(O.cache, "get_json", lambda ns, key, ttl: store.get((ns, key)))
    monkeypatch.setattr(O.cache, "put_json", lambda ns, key, value: store.__setitem__((ns, key), value))
    return store


def _wait(client, job_id, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/v1/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_object_info_runs_as_job_then_comes_from_cache(client, mem_cache, monkeypatch):
    async def basic(key):
        await asyncio.sleep(0.05)
        return {"main_id": key, "otype": "BY*", "plx_mas": 546.9759, "plx_err_mas": 0.04}

    async def summary(key):
        return {"lang": "tr", "title": "Barnard Yıldızı", "extract": "…", "url": "u", "wikidata": "Q"}

    monkeypatch.setattr(O.simbad, "object_basic", basic)
    monkeypatch.setattr(O.wiki, "summary", summary)
    r = client.get("/api/v1/objects/info", params={"main_id": "NAME Barnard's star"}).json()
    assert set(r) == {"job_id"}
    j = _wait(client, r["job_id"])
    assert j["status"] == "done" and j["result"]["sources"]["basic"] == "SIMBAD (CDS)"
    assert j["result"]["distance"]["pc"] == pytest.approx(1.828, abs=1e-3)
    step = j["steps"][0]
    assert step["step"] == "info_query" and isinstance(step["elapsed_s"], float)
    again = client.get("/api/v1/objects/info", params={"main_id": "NAME Barnard's star"}).json()
    assert again["from_cache"] is True and "job_id" not in again


def test_object_info_falls_back_to_sesame_and_reports_it(client, mem_cache, monkeypatch):
    async def down(key):
        raise UpstreamError("UPSTREAM_UNAVAILABLE", "simbad")

    async def no_wiki(key):
        raise UpstreamError("UPSTREAM_TIMEOUT", "wikimedia")

    async def ses(key, *a, **k):
        return {"main_id": key, "otype": "PM*"}

    monkeypatch.setattr(O.simbad, "object_basic", down)
    monkeypatch.setattr(O.wiki, "summary", no_wiki)
    monkeypatch.setattr(O.resolvers, "sesame", ses)
    job_id = client.get("/api/v1/objects/info", params={"main_id": "Proxima Centauri"}).json()["job_id"]
    j = _wait(client, job_id)
    assert [s["step"] for s in j["steps"]] == ["info_query", "info_fallback"]
    assert j["result"]["unavailable"] == ["SIMBAD", "Wikipedia"]
    assert "Sesame" in j["result"]["sources"]["basic"]


def test_similar_runs_as_job_and_survives_simbad_outage(client, mem_cache, monkeypatch):
    async def down(*a, **k):
        raise UpstreamError("UPSTREAM_UNAVAILABLE", "simbad")

    monkeypatch.setattr(O.simbad, "same_type", down)
    r = client.get("/api/v1/objects/similar", params={"main_id": "M 31", "otype": "AGN"}).json()
    j = _wait(client, r["job_id"])
    assert j["status"] == "done" and j["result"] == {"items": [], "unavailable": ["SIMBAD"]}


def test_websocket_announces_job_completion(client, mem_cache, monkeypatch):
    async def slow_basic(key):
        await asyncio.sleep(0.4)
        return {"main_id": key, "otype": "G"}

    async def summary(key):
        return None

    monkeypatch.setattr(O.simbad, "object_basic", slow_basic)
    monkeypatch.setattr(O.wiki, "summary", summary)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        job_id = client.get("/api/v1/objects/info", params={"main_id": "M 33"}).json()["job_id"]
        ws.send_json({"type": "subscribe", "topic": f"job:{job_id}"})
        seen = []
        for _ in range(10):
            m = ws.receive_json()
            seen.append(m["type"])
            if m["type"] == "job_done":
                assert m["job_id"] == job_id
                break
        assert "subscribed" in seen and seen[-1] == "job_done"
