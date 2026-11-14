""" "Görüntü bilgisi bulunamadı" (UNKNOWN_IMAGE): the image index lives in the disk cache, which a Render
deploy / restart wipes while pages stay open. Requests now re-index once at their own position."""

import asyncio
import time

import pytest

from skytracker.jobs import JobError
from skytracker.providers import spherex as S
from skytracker.services import time_compare as TC

RA, DEC = 269.45, 4.77
A = S.SpherexImage(
    "dr1:2025W33_2C_0321_1:D5",
    "dr1",
    "spherex_dr1",
    "2025W33_2C_0321_1",
    5,
    60912.0,
    60912.01,
    "2025-08-25T00:00:00Z",
    3.81,
    4.43,
    "https://irsa.ipac.caltech.edu/a.fits",
    None,
)
B = S.SpherexImage(
    "qr3:2026W38_1A_0100_1:D5",
    "qr3",
    "spherex_qr3",
    "2026W38_1A_0100_1",
    5,
    61305.0,
    61305.01,
    "2026-09-22T00:00:00Z",
    3.81,
    4.43,
    "https://irsa.ipac.caltech.edu/b.fits",
    None,
)


@pytest.fixture
def wiped_index(monkeypatch):
    """Empty index (as after a deploy); coverage() at the position registers DR1 and QR3 again."""
    index: dict[str, S.SpherexImage] = {}
    calls = []

    async def fake_coverage(ra, dec, progress=None):
        calls.append((ra, dec))
        index.update({A.image_id: A, B.image_id: B})
        return [A, B]

    monkeypatch.setattr(S, "get_image", lambda image_id: index.get(image_id))
    monkeypatch.setattr(S, "coverage", fake_coverage)
    return calls


def test_find_image_reindexes_once_and_finds_dr1_and_qr3(wiped_index):
    assert asyncio.run(S.find_image(A.image_id, RA, DEC)) == A
    assert asyncio.run(S.find_image(B.image_id, RA, DEC)) == B
    assert wiped_index == [(RA, DEC)]  # one coverage query re-registered both releases
    assert asyncio.run(S.find_image("dr1:nope:D5", RA, DEC)) is None


class Stop(Exception):
    pass


def test_mixed_dr1_a_qr3_b_comparison_survives_a_wiped_index(wiped_index, monkeypatch):
    seen = []

    async def fake_fetch(img, ra, dec, size):
        seen.append(img.release)
        raise Stop  # the lookup worked; the cutout download is not part of this test

    async def prog(*_):
        return None

    monkeypatch.setattr(S, "fetch_cutout_fits", fake_fetch)

    async def no_gaia(*_):
        return None

    monkeypatch.setattr(TC, "_gaia_field", no_gaia)  # no live ESA query from the test
    with pytest.raises(Stop):
        asyncio.run(TC.compare_time(A.image_id, B.image_id, RA, DEC, 0.1, "sub", True, None, prog))
    assert sorted(seen) == ["dr1", "qr3"] and len(wiped_index) == 1
    with pytest.raises(JobError) as e:  # an image that really is gone still reports it
        asyncio.run(TC.compare_time(A.image_id, "qr3:gone:D5", RA, DEC, 0.1, "sub", True, None, prog))
    assert e.value.code == "UNKNOWN_IMAGE"


def test_cutout_endpoint_no_longer_404s_after_a_wipe(client, wiped_index, monkeypatch):
    from skytracker.api.v1 import sky

    async def fake_build(img, ra, dec, size, zodi):
        return {"image_id": img.image_id, "release": img.release}

    monkeypatch.setattr(sky, "build_cutout", fake_build)
    r = client.post(
        "/api/v1/sky/cutout", json={"image_id": B.image_id, "ra": RA, "dec": DEC, "size_deg": 0.1}
    )
    assert r.status_code == 200  # a job, not 404 UNKNOWN_IMAGE
    for _ in range(100):
        j = client.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done" and j["result"]["release"] == "qr3"
    assert any(s["step"] == "reindex" for s in j["steps"])
