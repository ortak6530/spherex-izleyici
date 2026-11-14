"""Excel export: sheets, formula-injection guard, row cap, guest vs. signed-in, same-browser download."""

import datetime as dt
import io
import time

import pytest
from openpyxl import load_workbook

from skytracker.api.v1 import export as E
from skytracker.db import session_scope
from skytracker.db.models import Comparison, Event
from skytracker.providers import spherex as S
from skytracker.services import accounts as A
from skytracker.services import export_xlsx as X


def wait(client, job_id):
    for _ in range(200):
        j = client.get(f"/api/v1/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


TIME_RESULT = {
    "id": "cmp1",
    "a": {
        "date_obs": "2025-08-25T00:00:00Z",
        "release": "dr1",
        "detector": 5,
        "wavelength_um": 4.10,
        "fits_url": "https://irsa.ipac.caltech.edu/a.fits",
    },
    "b": {
        "date_obs": "2026-09-22T00:00:00Z",
        "release": "qr3",
        "detector": 5,
        "wavelength_um": 4.105,
        "fits_url": "https://irsa.ipac.caltech.edu/b.fits",
    },
    "channel": {"delta_um": 0.005, "ratio": 0.14, "status": "match"},
    "shift": {"px": 2.04, "arcsec": 12.5, "pa_deg": 347.0},
    "expected_shift": {"px": 1.82, "arcsec": 11.18},
    "photometry": {"a": None, "b": None, "change": None, "change_normalized": None},
    "dt_days": 393.0,
    "zodi": "sub",
    "size_deg": 0.1,
    "warnings": [{"code": "SATURATED_OR_MASKED_CORE", "epoch": "a"}, {"code": "NEW_UNKNOWN"}],
}


def test_safe_defuses_formulas_and_keeps_numbers():
    assert X.safe('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    for s in ("+1", "-2+3", "@SUM(A1)", "\tx"):
        assert X.safe(s).startswith("'")
    assert X.safe(-3.5) == -3.5 and X.safe(0) == 0 and X.safe(None) is None
    assert X.safe("M 31") == "M 31"
    assert X.safe("a\x00b\x07c") == "abc"  # characters Excel rejects are dropped


def test_filename_and_warning_text():
    today = dt.date(2026, 11, 14)
    assert X.filename_for(["Barnard Yıldızı"], today) == "barnard-yildizi_2026-11-14.xlsx"
    assert X.filename_for(["C/2025 N1 (ATLAS)"], today) == "c-2025-n1-atlas_2026-11-14.xlsx"
    assert X.filename_for(["M 31", "M 33"], today) == "cisim-listesi_2026-11-14.xlsx"
    assert X.filename_for(["ıııı"], today) == "iiii_2026-11-14.xlsx"
    assert "Dönem A" in X.warning_text({"code": "SATURATED_OR_MASKED_CORE", "epoch": "a"})
    assert X.warning_text({"code": "CHANNEL_WARN", "delta_um": 0.012, "ratio": 0.7}).count("12,0 nm") == 1
    assert X.warning_text({"code": "NEW_UNKNOWN"}) == "NEW_UNKNOWN"


def _book(objects):
    meta = {"generated_at": "2026-11-14 08:00:00", "site_url": "https://example.org", "filters_text": None}
    data, counts = X.build_workbook(objects, meta, [{"title": "SPHEREx", "text": "ack", "url": "https://s"}])
    return load_workbook(io.BytesIO(data)), counts


def test_workbook_sheets_links_and_injection():
    evil = "=cmd|'/c calc'!A0"
    obs = [
        [
            "2025-08-25T00:00:00Z",
            60912.0,
            "Ağustos 2025",
            "dr1",
            "D5",
            4.1,
            0.03,
            9,
            "3.811–4.430",
            "evet",
            evil,
            "R7",
            "https://irsa.ipac.caltech.edu/x.fits",
        ]
    ]
    wb, counts = _book(
        [
            {
                "name": evil,
                "target": {
                    "kind": "object",
                    "name": evil,
                    "ra": 269.45,
                    "dec": 4.69,
                    "main_id": "NAME Barnard",
                },
                "observations": obs,
                "n_observations": 1,
                "time_comparisons": [TIME_RESULT],
                "object_comparisons": [],
            }
        ]
    )
    assert wb.sheetnames == ["Özet", "Gözlemler", "Zaman karşılaştırması"]  # no empty sheets
    assert counts == {"Gözlemler": 1, "Zaman karşılaştırması": 1}
    g = wb["Gözlemler"]
    assert g["A3"].value == "'" + evil and g["L3"].value == "'" + evil
    assert g["A3"].data_type == "s"  # stored as text, never as a formula
    assert g["N3"].hyperlink.target == "https://irsa.ipac.caltech.edu/x.fits"
    assert g["G3"].value == 4.1  # numbers stay numbers
    z = wb["Zaman karşılaştırması"]
    header = [c.value for c in z[2]]
    row = dict(zip(header, [c.value for c in z[3]], strict=True))
    assert row["Kayma (″)"] == 12.5 and row["Kanal eşleşmesi"] == "Aynı kanal"
    assert row["Akı A (µJy)"] is None  # not measured -> empty, never invented
    assert "doymuş" in row["Uyarılar"] and "NEW_UNKNOWN" in row["Uyarılar"]
    ozet = wb["Özet"]
    texts = [c.value for r in ozet.iter_rows() for c in r if isinstance(c.value, str)]
    assert "ack" in texts and "'" + evil in texts
    for ws in wb.worksheets:  # nothing anywhere is a formula
        assert all(c.data_type != "f" for r in ws.iter_rows() for c in r)


def test_row_cap_is_noted(monkeypatch):
    monkeypatch.setattr(X, "MAX_ROWS", 3)
    rows = [
        ["2025-08-25", 1.0, None, "dr1", "D1", None, None, None, None, None, f"o{i}", None, None]
        for i in range(5)
    ]
    wb, counts = _book([{"name": "M 31", "observations": rows}])
    assert counts["Gözlemler"] == 3
    notes = [c.value for r in wb["Özet"].iter_rows() for c in r if isinstance(c.value, str)]
    assert any("2 satır eklenmedi" in n for n in notes)


def test_filters():
    f = E.ExportFilters(date_from="2025-09-01", releases=["qr3"], lam_min_um=1.0, lam_max_um=2.0)
    assert f.keep("2026-01-02T00:00:00Z", "qr3", 1.5)
    assert not f.keep("2025-08-30T00:00:00Z", "qr3", 1.5)
    assert not f.keep("2026-01-02", "dr1", 1.5)
    assert not f.keep("2026-01-02", "qr3", None)  # λ filter asked, λ unknown -> left out
    assert f.keep("2026-01-02", "qr3", None, use_lam=False)
    with pytest.raises(ValueError):
        E.ExportFilters(releases=["xx9"])


@pytest.fixture
def fake_target(monkeypatch):
    target = {
        "kind": "coordinate",
        "key": "coord-10.0000+20.0000",
        "name": "10.00000 +20.00000",
        "main_id": None,
        "query": "10 20",
        "ra": 10.0,
        "dec": 20.0,
        "source": "girdi",
    }

    async def fake_resolve(q):
        return dict(target, query=q)

    img = S.SpherexImage(
        "dr1:obs1:D2",
        "dr1",
        "c",
        "obs1",
        2,
        60912.0,
        60912.01,
        "2025-08-25T00:00:00Z",
        1.1033,
        1.6499,
        "https://irsa.ipac.caltech.edu/obs1.fits",
        None,
    )

    async def fake_cov(ra, dec, progress=None):
        return [img]

    async def fake_index(images, ra, dec, progress=None):
        return {"dr1:obs1:D2": {"wavelength_um": 1.25, "bandwidth_um": 0.03, "on_detector": True}}

    monkeypatch.setattr(E, "resolve_target", fake_resolve)
    monkeypatch.setattr(S, "coverage", fake_cov)
    monkeypatch.setattr(S, "index_wavelengths", fake_index)
    return target


def test_guest_exports_one_object_and_only_this_browser_downloads(client, fake_target):
    client.cookies.clear()
    client.get("/api/v1/health")
    r = client.post("/api/v1/export/xlsx", json={"items": [{"q": "a"}, {"q": "b"}]})
    assert r.status_code == 401 and r.json()["code"] == "LOGIN_REQUIRED_MULTI"

    sid = client.cookies.get("sid")
    with session_scope() as db:
        db.add(
            Comparison(
                id="exp-cmp-1",
                session_id=sid,
                kind="time",
                object_key=fake_target["key"],
                params={},
                result=dict(TIME_RESULT, id="exp-cmp-1"),
            )
        )
        db.add(
            Comparison(
                id="exp-cmp-2",
                session_id="someone-else",
                kind="time",
                object_key=fake_target["key"],
                params={},
                result=dict(TIME_RESULT, id="exp-cmp-2"),
            )
        )

    r = client.post("/api/v1/export/xlsx", json={"items": [{"q": "10 20", "d": 2}]})
    j = wait(client, r.json()["job_id"])
    assert j["status"] == "done", j
    res = j["result"]
    assert res["filename"] == f"10-00000-20-00000_{dt.datetime.now(dt.UTC).date().isoformat()}.xlsx"
    assert res["rows"] == {"Gözlemler": 1, "Zaman karşılaştırması": 1}  # the other browser's study is not in

    f = client.get(f"/api/v1/export/{res['file_id']}")
    assert f.status_code == 200
    assert f.headers["content-type"] == E.XLSX_MIME
    assert res["filename"] in f.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(f.content))
    assert wb["Gözlemler"]["G3"].value == 1.25
    assert wb["Zaman karşılaştırması"]["B3"].value == "exp-cmp-1"

    # downloads are logged even without analytics consent (admin feed)
    with session_scope() as db:
        ev = db.query(Event).filter(Event.type == "download", Event.session_id == sid).all()
        assert ev and ev[-1].payload["format"] == "xlsx" and ev[-1].ip_hash is None

    client.cookies.clear()
    client.get("/api/v1/health")  # another browser
    assert client.get(f"/api/v1/export/{res['file_id']}").status_code == 404


def test_signed_in_user_exports_several(client, fake_target, monkeypatch):
    box = []

    async def fake_deliver(email, code):
        box.append(code)
        return "server_log"

    monkeypatch.setattr(A, "deliver", fake_deliver)
    client.cookies.clear()
    client.get("/api/v1/health")
    client.post("/api/v1/auth/request-code", json={"email": "excel@example.org"})
    assert (
        client.post("/api/v1/auth/verify", json={"email": "excel@example.org", "code": box[-1]}).status_code
        == 200
    )
    r = client.post("/api/v1/export/xlsx", json={"items": [{"q": "10 20"}, {"q": "10 20 "}]})
    j = wait(client, r.json()["job_id"])
    assert j["status"] == "done", j
    assert j["result"]["filename"].startswith("cisim-listesi_")
    assert j["result"]["rows"]["Gözlemler"] == 2
