"""Motion-track layer: expected positions (2010.0, 2016.0, A, B) and measured centroids on A's grid."""

from types import SimpleNamespace

from astropy.wcs import WCS

from skytracker.domain.astrometry import jyear_to_mjd
from skytracker.services.time_compare import motion_track


def grid(ra=269.45, dec=4.70, scale_arcsec=6.15):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [30.5, 30.5]  # 1-based FITS -> pixel 29.5 (0-based) is the centre
    w.wcs.cdelt = [-scale_arcsec / 3600, scale_arcsec / 3600]
    return w


PM = {"ra_j2000": 269.452, "dec_j2000": 4.6934, "pmra_mas_yr": -801.5, "pmdec_mas_yr": 10362.4}


def test_track_follows_proper_motion_in_time_order():
    ea = SimpleNamespace(wcs=grid(), mjd=jyear_to_mjd(2025.65))
    eb = SimpleNamespace(wcs=grid(), mjd=jyear_to_mjd(2026.72))
    shift = {"a_centroid": [269.4461, 4.7690], "b_centroid": [269.4458, 4.7721]}
    t = motion_track(PM, ea, eb, shift)
    assert [p["label"] for p in t["expected"]] == ["2010.0", "2016.0", "A", "B"]
    ys = [p["px"][1] for p in t["expected"]]
    assert ys == sorted(ys)  # Barnard moves north (+y on this grid)
    # 2010 -> 2016: 6 yr x 10.39"/yr = 62" = ~10 px of 6.15"
    assert abs((ys[1] - ys[0]) - 6 * 10.3624 / 6.15) < 0.3
    assert [m["label"] for m in t["measured"]] == ["A", "B"]
    assert "ölçüm değildir" in t["note"]


def test_no_track_without_proper_motion():
    e = SimpleNamespace(wcs=grid(), mjd=60900.0)
    assert motion_track(None, e, e, None) is None
    assert (
        motion_track(
            {"ra_j2000": 10.0, "dec_j2000": 41.0, "pmra_mas_yr": None, "pmdec_mas_yr": None}, e, e, None
        )
        is None
    )
