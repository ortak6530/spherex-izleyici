"""Live position: rise/set from an altitude series, Horizons command rules and parsing, proper motion,
cities list and one live job per browser."""

import datetime as dt
import time

import numpy as np

from skytracker.api.v1 import live as API
from skytracker.services import live as L

T0 = dt.datetime(2026, 11, 14, 0, 0, tzinfo=dt.UTC)
HORIZONS_SAMPLE = """
*******************************************************************************
Target body name: ATLAS (C/2025 N1)               {source: JPL#55}
 Date__(UT)__HR:MN, , , R.A._(ICRF), DEC_(ICRF), Azi_(a-app), Elev_(a-app), T-mag, N-mag, delta, deldot,
*******************************************************************************
$$SOE
 2026-Nov-14 07:00,*, , 359.90, 19.30184, 281.888792, 16.110558, 25.758, n.a., 12.7176441628054, 34.5671070,
 2026-Nov-14 07:30,*, , 0.10, 19.30192, 286.387437, 10.518448, 25.758, n.a., 12.7180600584072, 34.5754518,
$$EOE
"""


def test_rise_set_and_circumpolar_from_series():
    times = [T0 + dt.timedelta(hours=h) for h in range(25)]
    alt = np.array([-10 + 20 * np.sin(np.pi * (h - 6) / 12) for h in range(25)], float)  # 0° at 08 h, 16 h
    ev = L._events(times, alt, np.full(25, 180.0))
    assert ev["rise"]["utc"] == "2026-11-14T08:00:00Z" and ev["set"]["utc"] == "2026-11-14T16:00:00Z"
    assert ev["transit"]["utc"] == "2026-11-14T12:00:00Z" and not ev["always_up"] and not ev["never_up"]
    assert L._events(times, np.full(25, 30.0), np.zeros(25))["always_up"]
    none = L._events(times, np.full(25, -5.0), np.zeros(25))
    assert none["never_up"] and none["rise"] is None and none["set"] is None


def test_horizons_command_rules_verified_live():
    assert L.horizons_command("433") == ["'433;'"]  # numbered asteroid; 'DES=433;' is another body
    assert L.horizons_command("1P") == ["'DES=1P;CAP;'", "'DES=1P;'"]
    assert L.horizons_command("2024 YR4")[-1] == "'DES=2024 YR4;'"  # CAP fails for asteroids


def test_parse_and_interpolate_across_ra_zero():
    rows = L._parse_horizons(HORIZONS_SAMPLE)
    assert len(rows) == 2 and rows[0]["mag"] == 25.758 and rows[0]["el"] == 16.110558
    p = L.interpolate(rows, rows[0]["t"] + dt.timedelta(minutes=15))
    assert abs(p["ra"] - 0.0) < 1e-6 or abs(p["ra"] - 360.0) < 1e-6  # 359.9 -> 0.1 passes through 0, not 180
    assert abs(p["el"] - (16.110558 + 10.518448) / 2) < 1e-9


def test_star_now_uses_proper_motion():
    barnard = {
        "kind": "object",
        "ra_j2000": 269.452,
        "dec_j2000": 4.6934,
        "pmra_mas_yr": -801.5,
        "pmdec_mas_yr": 10362.4,
        "ra": 269.45,
        "dec": 4.77,
    }
    p = L.star_now(barnard, T0)
    years = (T0 - dt.datetime(2000, 1, 1, 12, tzinfo=dt.UTC)).days / 365.25
    assert abs(p["moved_since_j2000_arcsec"] - 10.393 * years) < 1.0  # ~10.39"/yr
    galaxy = {
        "kind": "object",
        "ra_j2000": 10.68,
        "dec_j2000": 41.27,
        "pmra_mas_yr": None,
        "pmdec_mas_yr": None,
    }
    assert L.star_now(galaxy, T0)["moved_since_j2000_arcsec"] is None


def test_cities_come_from_wikidata(client):
    body = client.get("/api/v1/live/cities").json()
    names = [c["name"] for c in body["cities"]]
    assert "Ankara" in names and body["source"].startswith("Wikidata")
    assert all(c["wikidata"].startswith("Q") and -90 <= c["lat"] <= 90 for c in body["cities"])


def test_one_live_job_per_browser(client, monkeypatch):
    async def fake_resolve(q):
        return {"kind": "object", "name": q, "ra": 10.0, "dec": 20.0}

    async def fake_snapshot(target, site, when=None):
        return {"ra": 10.0, "dec": 20.0, "site": site}

    monkeypatch.setattr(API, "resolve_target", fake_resolve)
    monkeypatch.setattr(API.L, "snapshot", fake_snapshot)
    monkeypatch.setattr(API, "INTERVAL_S", 0.05)
    client.cookies.clear()
    client.get("/api/v1/health")
    assert client.post("/api/v1/live/start", json={"q": "x", "city": "Atlantis"}).status_code == 400
    first = client.post("/api/v1/live/start", json={"q": "M31", "city": "Ankara"}).json()["job_id"]
    time.sleep(0.2)
    second = client.post("/api/v1/live/start", json={"q": "M33", "lat": 40.0, "lon": 30.0}).json()["job_id"]
    for _ in range(100):
        j = client.get(f"/api/v1/jobs/{first}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done" and j["result"]["ended"]  # superseded by the second one
    steps = [s for s in j["steps"] if s["step"] == "position"]
    assert steps and steps[0]["position"]["site"]["name"] == "Ankara"
    s2 = client.get(f"/api/v1/jobs/{second}").json()
    assert s2["status"] == "running"
    pos = [s for s in s2["steps"] if s["step"] == "position"]
    assert pos and pos[-1]["position"]["site"] == {"name": None, "lat": 40.0, "lon": 30.0, "source": "girdi"}
    API._current.clear()  # stop it
