"""NEOSSat via CADC CAOM TAP: query shape (object frames only), CORD > COR > RAW (no CLEAN), datalink."""

import asyncio

from skytracker.providers import neossat as N

CSV = (
    "observationID,target_name,productID,publisherID,time_bounds_lower,time_exposure\n"
    "o1,M31,clean,ivo://cadc.nrc.ca/NEOSSAT?o1/clean,59390.94,60.0\n"
    "o1,M31,raw,ivo://cadc.nrc.ca/NEOSSAT?o1/raw,59390.94,60.0\n"
    "o2,M31,raw,ivo://cadc.nrc.ca/NEOSSAT?o2/raw,59391.00,60.0\n"
    "o2,M31,cord,ivo://cadc.nrc.ca/NEOSSAT?o2/cord,59391.00,60.0\n"
    "o2,M31,cor,ivo://cadc.nrc.ca/NEOSSAT?o2/cor,59391.00,60.0\n"
    "o3,M31,clean,ivo://cadc.nrc.ca/NEOSSAT?o3/clean,59392.00,60.0\n"
)
DL = (
    "<VOTABLE><TABLE><DATA><TABLEDATA>"
    "<TR><TD>ivo://x</TD><TD>https://cadc-west-01.canfar.net/raven/files/cadc:NEOSSAT/o2_prev.png</TD>"
    "<TD>#preview</TD></TR>"
    "<TR><TD>ivo://x</TD><TD>https://cadc-west-01.canfar.net/raven/files/cadc:NEOSSAT/o2.fits</TD>"
    "<TD>#this</TD></TR></TABLEDATA></DATA></TABLE></VOTABLE>"
)


def test_query_keeps_object_frames_of_the_collection():
    q = N.adql(10.6847, 41.269)
    assert "o.collection = 'NEOSSAT'" in q and "o.type = 'object'" in q  # darks left out (guide)
    assert "INTERSECTS(POINT('ICRS', 10.684700, 41.269000), p.position_bounds) = 1" in q


def test_product_preference_and_no_clean():
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(CSV)))
    picked = N.pick_products(rows)
    assert [(r["observationID"], r["productID"]) for r in picked] == [
        ("o2", "cord"),
        ("o1", "raw"),
    ]  # o3: only CLEAN


class R:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def test_search_with_datalink_links(monkeypatch):
    async def fake_get(url, params=None, **_):
        return R(DL) if url == N.DATALINK else R(CSV)

    monkeypatch.setattr(N.http, "get", fake_get)
    monkeypatch.setattr(N.cache, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(N.cache, "put_json", lambda *a, **k: None)
    out = asyncio.run(N.search(10.6847, 41.269))
    first = out["items"][0]
    assert first["observation_id"] == "o2" and first["product"] == "cord" and not first["raw_warning"]
    assert first["preview"].endswith("o2_prev.png") and first["fits"].endswith("o2.fits")
    assert out["items"][1]["raw_warning"] is True
    assert "FILTER = CLEAR" in out["note"] and "konum doğruluğu sınırlıdır" in out["note"]
    assert out["n_observations"] == 2 and out["truncated"] is False
