"""IRSA MOST parsing: frames -> active releases only, image index registration, thinned ephemeris."""

from astropy.table import Table

from skytracker.providers import most
from skytracker.providers import spherex as S

URI = "ibe/data/spherex/{rel}/level2/2025W50_2A/l2b-v27-2026-300/5/level2_2025W50_2A_0685_{n}D5_spx.fits"


def _frames(rows):
    cols = ["match", "uri", "productid", "observationid", "mjd_start", "mjd_end", "ra_obj", "dec_obj"]
    cols += ["sun_dist", "geo_dist", "phase", "vmag", "dist_ctr"]
    return Table(rows=rows, names=cols)


def _row(rel, n, mjd, match="1"):
    return (match, URI.format(rel=rel, n=n), "D5", f"2025W50_2A_0685_{n}", mjd, mjd + 0.0013,
            167.27, 5.12, 2.144, 1.808, 27.2, 13.1, 0.4)  # fmt: skip


def test_parse_frames_keeps_active_releases_sorted_by_time():
    rows = [_row("dr1", 2, 61023.2), _row("dr1", 1, 61023.1), _row("qr2", 3, 61023.3), _row("dr1", 4, 1, "0")]
    t = _frames(rows)
    frames, skipped = most.parse_frames(t)
    assert [f.obs_id for f in frames] == ["2025W50_2A_0685_1", "2025W50_2A_0685_2"]
    assert skipped == {"qr2": 1}  # superseded release is never used for new results
    f = frames[0]
    assert f.image_id == "dr1:2025W50_2A_0685_1:D5" and f.release == "dr1" and f.detector == 5
    assert f.fits_url.startswith("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/")
    assert f.date_obs.endswith("Z") and f.vmag == 13.1


def test_register_makes_frame_available_for_cutouts():
    frames, _ = most.parse_frames(_frames([_row("dr1", 7, 61023.5)]))
    most._register(frames[0])
    img = S.get_image(frames[0].image_id)
    assert img is not None and img.detector == 5
    assert (img.em_min_um, img.em_max_um) == most.DETECTOR_RANGE_UM[5]
    assert img.s3_key and img.s3_key.startswith("dr1/level2/")


def test_parse_track_thins_to_one_point_per_day():
    eph = Table(
        rows=[(2461000.5 + 0.25 * i, 160.0 + i * 0.1, 5.0, 2.0, 1.8, 13.0) for i in range(12)],
        names=["JD", "RA_obs", "Dec_obs", "HelioDist", "GeoDist", "Vmag"],
    )
    track = most.parse_track(eph)
    assert len(track) == 3 and track[1]["mjd"] - track[0]["mjd"] == 1.0
    assert most.parse_track(None) == []


def test_designation_validation():
    assert most.DESIGNATION_RE.match("2025 N1") and most.DESIGNATION_RE.match("2P")
    assert not most.DESIGNATION_RE.match("../etc") and not most.DESIGNATION_RE.match("x;rm")


def test_moving_endpoint_rejects_bad_input(client):
    assert client.get("/api/v1/moving/x;rm/frames").status_code == 400
    r = client.get("/api/v1/moving/2P/frames", params={"start": "2026-01-01", "end": "2025-01-01"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_DATE"
