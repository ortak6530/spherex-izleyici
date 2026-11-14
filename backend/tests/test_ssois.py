"""CADC SSOIS: bynameCADC query (upper-case, tsv), comets not covered, TSV / not-found parsing, summary."""

import asyncio

from skytracker.providers import ssois as SS

TSV = (
    "Image\tMJD\tFilter\tExptime\tObject_RA\tObject_Dec\tImage_target\tTelescope/Instrument\tDatalink\n"
    "a1\t60951.25\tBand-7\t1216\t29.11\t42.80\t433_Eros\tALMA\t\n"
    "b2\t52544.96\tunknown\t10\t337.38\t14.32\tx\tINT/WFC\thttp://casu.ast.cam.ac.uk/x?a=1&amp;b=2\n"
    "c3\t55000.5\tr\t60\t1.0\t2.0\ty\tCFHT/MegaCam\thttps://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/x?a=1&amp;b=2\n"
)
NOT_FOUND = "Object 'C/2025 N1' not found.<br/>\nThere several possible reasons:\n<ul>…"


def test_query_name_rules_verified_live():
    assert SS.query_name("433", "an") == "433"
    assert SS.query_name("2024 yr4", "au") == "2024 YR4"  # upper case
    assert SS.query_name("eros") == "EROS"
    # MPCORB.DAT has no comets: 3I/ATLAS (des "2025 N1", SBDB kind "cu"), 1P, 2P/Encke, C/2025 N1
    assert SS.query_name("2025 N1", "cu") is None
    for des in ("1P", "2P/Encke", "C/2025 N1", "3I"):
        assert SS.query_name(des) is None


def test_parse_and_summary():
    rows, nf = SS.parse_tsv(TSV)
    assert len(rows) == 3 and not nf
    s = SS.summarise(rows)
    assert s["total"] == 3 and s["first"] == "2002-09-27" and s["last"] == "2025-10-03"  # MJD 60951.25
    assert s["recent"][0]["instrument"] == "ALMA"  # newest first
    links = [r["link"] for r in s["recent"]]
    assert "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/x?a=1&b=2" in links  # &amp; unescaped
    assert not any(link and link.startswith("http://") for link in links)  # http is not shown as a link
    assert SS.parse_tsv(NOT_FOUND) == ([], True)


class R:
    status_code = 200

    def __init__(self, text):
        self.text = text


def test_search_sends_bynamecadc_tsv_and_never_queries_comets(monkeypatch):
    sent = []

    async def fake_get(url, params=None, **_):
        sent.append((url, params))
        return R(TSV)

    monkeypatch.setattr(SS.http, "get", fake_get)
    monkeypatch.setattr(SS.cache, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(SS.cache, "put_json", lambda *a, **k: None)
    out = asyncio.run(SS.search("433", "an"))
    url, p = sent[0]
    assert url.endswith("/cadcbin/ssos/ssosclf.pl")
    assert p["search"] == "bynameCADC" and p["format"] == "tsv" and p["object"] == "433"
    assert p["eunits"] == "arcseconds"  # any other value -> HTTP 500 (verified)
    assert out["status"] == "ok" and out["total"] == 3 and "görünür" in out["note"]
    c = asyncio.run(SS.search("2025 N1", "cu"))
    assert c["status"] == "not_covered" and len(sent) == 1  # no request for a comet
