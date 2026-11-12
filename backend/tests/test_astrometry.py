import pytest

from skytracker.domain.astrometry import SEARCH_EPOCH, jyear_to_mjd, propagate


def test_no_motion_is_identity():
    assert propagate(10.0, 20.0, None, None, jyear_to_mjd(2026.0)) == (10.0, 20.0)


def test_barnards_star_moves_about_4_4_arcmin_by_2026():
    # SIMBAD J2000: 269.45207696, +4.69336497; pmra=-801.551, pmdec=10362.394 mas/yr
    ra, dec = propagate(269.4520769586187, 4.69336496657667, -801.551, 10362.394, jyear_to_mjd(SEARCH_EPOCH))
    assert (dec - 4.69336496657667) * 3600 == pytest.approx(10.362394 * 26, rel=1e-6)
    assert ra < 269.4520769586187  # moving west


def test_ra_wraps():
    ra, _ = propagate(359.9999, 0.0, 100_000, 0, jyear_to_mjd(2026.0))
    assert 0 <= ra < 1
