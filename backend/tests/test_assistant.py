"""Rule-based assistant: FAQ matching (Turkish normalisation), real-value interpretation, object
opening, ownership of comparisons, streaming over the job topic."""

import asyncio
import time

import pytest

from skytracker.api.v1 import assistant as API
from skytracker.db import session_scope
from skytracker.db.models import Comparison, Event
from skytracker.providers import names
from skytracker.services import assistant as AS
from skytracker.services import freshness as FR

TIME_RESULT = {
    "id": "a1",
    "kind": "time",
    "a": {"date_obs": "2025-08-25T00:00:00Z", "release": "dr1", "detector": 5, "wavelength_um": 4.10},
    "b": {"date_obs": "2026-09-22T00:00:00Z", "release": "qr3", "detector": 5, "wavelength_um": 4.105},
    "channel": {"delta_um": 0.005, "ratio": 0.14, "status": "match"},
    "shift": {"px": 2.04, "arcsec": 12.5, "pa_deg": 347.0},
    "expected_shift": {"px": 1.82, "arcsec": 11.18},
    "photometry": {"a": None, "b": None, "change": None, "change_normalized": None},
    "dt_days": 393.0,
    "warnings": [{"code": "SATURATED_OR_MASKED_CORE", "epoch": "a"}],
}


def ask(message=None, quick=None, ctx=None):
    return asyncio.run(AS.RuleBasedAssistant().answer(message, quick, ctx or AS.Context()))


def test_faq_file_is_consistent():
    data = AS.faq()
    ids = [e["id"] for e in data["entries"]]
    assert len(ids) == len(set(ids))
    for e in data["entries"]:
        assert e["answer"].strip() and e["keywords"]
        assert all(r in ids for r in e.get("related", [])), e["id"]
    assert all(i in ids for i in data["suggest_after_fallback"])
    labels = [q["label"] for q in AS.quick_buttons()]
    # the buttons the user asked for (2026-11-14), then the two dynamic ones
    assert labels == [
        "SPHEREx nedir?",
        "Bu görüntüdeki renkler ne anlama geliyor?",
        "Zaman karşılaştırmasını nasıl kullanırım?",
        "Hareketli cisim nedir, 3I/ATLAS neden özel?",
        "Veri nereden geliyor, ne kadar güncel?",
        "Karşılaştırmayı yorumla",
        "Seçili cisim",
    ]
    # no fixed archive date or invented percentage in the hand-written answers
    raw = (AS.get_settings().config_dir / "assistant_faq.json").read_text("utf-8")
    assert "2026-10" not in raw and "Ekim 2026" not in raw and "%" not in raw
    # Hubble <-> Webb was cancelled (DECISIONS §4g): no answer may promise it
    assert "MAST" not in raw and "yan yana görünümü" not in raw and "hubble_webb" not in raw


@pytest.mark.parametrize(
    ("message", "entry"),
    [
        ("Görüntü neden pikselli?", "faq:pixelated"),
        ("GORUNTU NEDEN PIKSELLI", "faq:pixelated"),
        ("SPHEREx nedir?", "faq:spherex"),
        ("zaman karşılaştırması nasıl yapılır", "faq:timecompare"),
        ("koordinatla nasıl arama yaparım", "faq:search"),
        ("gri pikseller ne anlama geliyor", "faq:grey"),
        ("kuyruklu yıldızları nasıl izliyorsunuz", "faq:moving"),
        ("3I/ATLAS neden bu kadar özel", "faq:moving"),
        ("renkler ne demek", "faq:colors"),
        ("veriler ne kadar güncel", "faq:data"),
        ("hubble ile webb karşılaştırması", "fallback"),  # cancelled feature -> "Bunu bilmiyorum"
    ],
)
def test_free_text_matching(message, entry):
    assert ask(message).source == entry


def test_greeting_fallback_and_suggestions():
    assert ask("Merhaba").source == "greeting"
    a = ask("qwerty zxcv")
    assert a.source == "fallback" and a.action is None
    assert a.text.startswith("Bunu bilmiyorum")
    assert [s["id"] for s in a.suggestions] == [
        "spherex",
        "colors",
        "timecompare",
        "moving",
        "data",
    ]


def test_freshness_comes_from_the_live_check_never_hard_coded():
    f = {
        "newest": {"date_utc": "2026-10-05T00:01:59Z", "release": "QR3", "mjd": 61318.0},
        "per_release": {
            "dr1": {"date_utc": "2026-05-14T11:47:39Z", "release": "DR1"},
            "qr3": {"date_utc": "2026-10-05T00:01:59Z", "release": "QR3"},
        },
        "checked_at": "2026-11-14T06:40:00Z",
        "source": "IRSA TAP (spherex.obscore)",
    }
    t = ask(quick="data", ctx=AS.Context(freshness=f)).text
    assert "en yeni SPHEREx gözlemi: 2026-10-05 (QR3)" in t and "DR1: 2026-05-14" in t
    assert "2026-11-14 06:40:00 UTC" in t
    pending = ask("veriler ne kadar güncel").text  # first check still running
    assert "okunuyor" in pending and "2026" not in pending


def test_answers_adapt_to_the_open_object():
    obj = {"name": "Barnard's star", "kind": "object"}
    info = {"simbad": {"otype_desc": "BY Dra Variable"}}
    t = ask(quick="colors", ctx=AS.Context(object=obj, object_info=info, n_images=358)).text
    assert "Şu an açık: Barnard's star (BY Dra Variable)" in t and "358 görüntü" in t
    t = ask(quick="timecompare", ctx=AS.Context(object=obj)).text
    assert "Şu an açık: Barnard's star" in t and "henüz hesaplanmadı" in t  # count unknown -> said so
    assert "Şu an açık" not in ask(quick="colors").text  # nothing open -> generic answer
    sol = {"name": "C/2025 N1 (ATLAS)", "kind": "solar_system", "orbit_class": "Hyperbolic Comet"}
    assert "364 kare" in ask(quick="object", ctx=AS.Context(object=sol, n_images=364)).text


def test_object_named_in_message_is_opened():
    a = ask("andromeda hakkında anlat")
    assert a.action == {"type": "open_object", "q": "M31"}
    assert names.find_in_text("ayni kanal ne demek") is None  # whole words only


def test_interpret_needs_a_comparison_and_never_invents():
    assert ask(quick="interpret").source == "faq:interpret"
    assert "Önce bir karşılaştırma yap" in ask(quick="interpret").text
    a = ask(quick="interpret", ctx=AS.Context(comparison=TIME_RESULT))
    assert a.source == "interpret"
    assert "12,50″" in a.text and "2,04 piksel" in a.text
    assert "11,18″" in a.text and "uyumlu ✓" in a.text  # |2.04 - 1.82| = 0.22 px
    assert "ölçülemedi" in a.text  # photometry missing -> said so, no number
    assert "doymuş veya maskeli" in a.text  # warning text from the server's code
    assert "%" not in a.text  # no brightness percentage was computed, none is shown


def test_interpret_object_comparison():
    c = {
        "kind": "object",
        "objects": {
            "a": {"name": "WISE 0855", "otype": "BD*", "otype_desc": "Brown Dwarf"},
            "b": {"name": "Luhman 16", "otype": "**", "otype_desc": "Double or Multiple Star"},
        },
        "same_type": False,
        "a_view": {
            "detector": 6,
            "wavelength_um": 4.736,
            "photometry": {"flux_ujy": 562.0, "err_ujy": 236.0},
            "ab_mag": 17.03,
        },
        "b_view": {
            "wavelength_um": 4.740,
            "photometry": {"flux_ujy": 150047.0, "err_ujy": 4580.0},
            "ab_mag": 10.96,
        },
        "channel": {"status": "match"},
        "flux_ratio_b_over_a": 267.0,
        "warnings": [],
    }
    t = ask(quick="interpret", ctx=AS.Context(comparison=c)).text
    assert "farklı türler" in t and "AB 17,03" in t and "267,00 kat parlak" in t


def test_selected_object_from_server_info():
    obj = {"name": "Barnard's star", "kind": "object", "main_id": "NAME Barnard's star"}
    info = {
        "simbad": {
            "otype_desc": "BY Dra Variable",
            "sp_type": "M4V",
            "pmra_mas_yr": -801.5,
            "pmdec_mas_yr": 10362.5,
        },
        "distance": {"pc": 1.828, "ly": 5.963, "method": "1/paralaks"},
        "wikipedia": None,
    }
    t = ask(quick="object", ctx=AS.Context(object=obj, object_info=info)).text
    assert "M4V" in t and "6,0 ışık yılı" in t and "10,39″" in t
    assert "Henüz bir cisim seçmedin" in ask(quick="object").text


def test_chunks_rebuild_the_text():
    t = "Bir iki üç dört beş altı yedi.\n\nSekiz dokuz on."
    assert "".join(AS.chunks(t)) == t and len(AS.chunks(t)) > 1


def wait(client, job_id):
    for _ in range(200):
        j = client.get(f"/api/v1/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_api_streams_and_reads_only_own_comparisons(client, monkeypatch):
    monkeypatch.setattr(API, "SUBSCRIBE_WAIT_S", 0)
    monkeypatch.setattr(API, "CHUNK_DELAY_S", 0)
    client.cookies.clear()
    client.get("/api/v1/health")
    sid = client.cookies.get("sid")
    with session_scope() as db:
        db.add(
            Comparison(
                id="ab12",
                session_id=sid,
                kind="time",
                object_key="barnard",
                params={},
                result=dict(TIME_RESULT, id="ab12"),
            )
        )
        db.add(
            Comparison(
                id="cd34",
                session_id="another-browser",
                kind="time",
                object_key="barnard",
                params={},
                result=dict(TIME_RESULT, id="cd34", shift={"px": 9.0, "arcsec": 55.5}),
            )
        )

    assert client.get("/api/v1/assistant/quick").json()["items"][0]["id"] == "spherex"
    assert client.post("/api/v1/assistant/message", json={}).status_code == 400

    r = client.post(
        "/api/v1/assistant/message", json={"quick": "interpret", "context": {"object": {"key": "barnard"}}}
    )
    j = wait(client, r.json()["job_id"])
    assert j["status"] == "done"
    streamed = "".join(s["text"] for s in j["steps"] if s["step"] == "assistant_chunk")
    assert streamed and j["result"]["text"].startswith(streamed[:40])
    assert "12,50″" in j["result"]["text"]

    # another browser's comparison id is not readable -> "önce bir karşılaştırma yap"
    r = client.post(
        "/api/v1/assistant/message", json={"quick": "interpret", "context": {"comparison_id": "cd34"}}
    )
    j = wait(client, r.json()["job_id"])
    assert "55,50″" not in j["result"]["text"] and "Önce bir karşılaştırma yap" in j["result"]["text"]


def test_admin_log_gets_only_assistant_question(client, monkeypatch):
    monkeypatch.setattr(API, "SUBSCRIBE_WAIT_S", 0)
    monkeypatch.setattr(API, "CHUNK_DELAY_S", 0)
    client.cookies.clear()
    client.get("/api/v1/health")
    client.cookies.set("spx_consent", "all")  # visitor accepted analytics
    sid = client.cookies.get("sid")
    secret = "Barnard yıldızı gizli sorum xyz123"
    r = client.post(
        "/api/v1/assistant/message",
        json={"message": secret, "context": {"object": {"key": "barnard", "name": "Barnard"}}},
    )
    wait(client, r.json()["job_id"])
    with session_scope() as db:
        evs = db.query(Event).filter(Event.session_id == sid).all()
        mine = [e for e in evs if e.type == "assistant_question"]
        assert len(mine) == 1 and mine[0].payload is None and mine[0].object_key is None
        assert all("xyz123" not in str(e.payload) and "xyz123" not in str(e.page) for e in evs)


def test_freshness_check_reads_tap_and_keeps_the_newest(monkeypatch):
    rows = {"spherex_dr1": "61174.491426,2026W20_1A_1245_1", "spherex_qr3": "61318.001388,2026W40_2B_0001_1"}

    class R:
        status_code = 200

        def __init__(self, text):
            self.text = text

    async def fake_get(url, params=None, **_):
        coll = params["QUERY"].split("'")[1]
        return R("t_min,obs_id\n" + rows[coll])

    monkeypatch.setattr(FR.http, "get", fake_get)
    monkeypatch.setattr(FR.cache, "put_json", lambda *a, **k: None)
    s = asyncio.run(FR.refresh())
    assert s["newest"]["release"] == "QR3" and s["newest"]["date_utc"].startswith("2026-10-05")
    assert s["per_release"]["dr1"]["date_utc"].startswith("2026-05-14")
    assert FR.latest() is s


def test_freshness_survives_a_deploy_via_the_database(client, monkeypatch):
    """A deploy wipes memory and the disk cache; the database copy is shown at once at start-up."""

    class R:
        status_code = 200
        text = "t_min,obs_id\n61318.001388,2026W40_2B_0001_1"

    async def fake_get(url, params=None, **_):
        return R()

    monkeypatch.setattr(FR.http, "get", fake_get)
    monkeypatch.setattr(FR.cache, "put_json", lambda *a, **k: None)
    asyncio.run(FR.refresh())  # stored in app_state
    monkeypatch.setattr(FR, "_state", None)  # "new process": memory empty …
    monkeypatch.setattr(FR.cache, "get_json", lambda *a, **k: None)  # … and disk wiped
    assert FR.latest() is None
    saved = asyncio.run(FR.load_saved())
    assert saved and saved["newest"]["date_utc"].startswith("2026-10-05")
    assert FR.latest()["checked_at"] == saved["checked_at"]  # shown with when it was checked
    assert 0 <= FR._age_s(saved) < 60
