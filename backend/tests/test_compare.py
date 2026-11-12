import numpy as np
import pytest

from skytracker.domain import compare as C


def gaussian(shape, cx, cy, amp=10.0, sigma=1.0, bg=1.0):
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    return bg + amp * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))


def test_bilinear_identity_and_masking():
    img = np.arange(25, dtype=float).reshape(5, 5)
    bad = np.zeros_like(img, bool)
    yy, xx = np.mgrid[0:4, 0:4].astype(float)
    out = C.bilinear_sample(img, bad, xx + 0.5, yy)
    assert np.allclose(out, img[:4, :4] + 0.5)
    bad[1, 1] = True
    out = C.bilinear_sample(img, bad, np.array([0.5]), np.array([0.5]))
    assert np.isnan(out[0])


def test_centroid_recovers_subpixel_shift():
    a = gaussian((31, 31), 15.0, 15.0)
    b = gaussian((31, 31), 15.6, 14.7)
    bad = np.zeros_like(a, bool)
    ca = C.centroid(a, bad, 15, 15, r=3, bg=1.0)
    cb = C.centroid(b, bad, 15, 15, r=3, bg=1.0)
    assert ca == pytest.approx((15.0, 15.0), abs=0.02)
    assert cb[0] - ca[0] == pytest.approx(0.6, abs=0.08)
    assert cb[1] - ca[1] == pytest.approx(-0.3, abs=0.08)


def test_centroid_survives_saturated_nan_core():
    a = gaussian((31, 31), 15.3, 15.0, amp=50, sigma=1.5)
    a[14:17, 14:17] = np.nan  # IRSA sets early-overflow pixels to NaN
    c = C.centroid(a, np.zeros_like(a, bool), 15, 15, r=4, bg=1.0)
    assert c is not None and abs(c[0] - 15.3) < 0.2


def test_aperture_flux_and_percent_change():
    a = gaussian((31, 31), 15, 15, amp=10)
    b = gaussian((31, 31), 15, 15, amp=11)  # 10 % brighter
    var = np.full_like(a, 1e-4)
    bad = np.zeros_like(a, bool)
    fa = C.aperture_flux(a, var, bad, 15, 15, omega_arcsec2=37.8)
    fb = C.aperture_flux(b, var, bad, 15, 15, omega_arcsec2=37.8)
    assert fa["background_mjy_sr"] == pytest.approx(1.0, abs=0.01)
    pc = C.percent_change(fa, fb)
    assert pc["percent"] == pytest.approx(10.0, abs=0.5)
    assert pc["err_percent"] > 3.0  # includes the 3 % systematic per epoch


def test_relative_scale_ignores_target_core():
    rng = np.random.default_rng(1)
    field = rng.uniform(1, 10, (40, 40))
    a = field.copy()
    b = field / 1.25  # calibration offset of 25 %
    core = C.disk_mask(a.shape, 20, 20, 4)
    a[core] *= 3  # the target itself changed a lot
    assert C.relative_scale(a, b, core) == pytest.approx(1.25, rel=1e-6)


@pytest.mark.parametrize("dl,status", [(0.010, "match"), (0.035, "warn"), (0.08, "reject")])
def test_channel_match(dl, status):
    assert C.channel_match(2.44, 2.44 + dl, 0.05, 0.05)["status"] == status


def test_atmospheric_lines():
    assert "He I 1.083 µm" in C.nearby_lines(1.09, 0.03)
    assert C.nearby_lines(2.2, 0.05) == []


def test_background_none_when_everything_is_source():
    img = np.ones((20, 20))
    assert C.robust_background(img, np.zeros_like(img, bool)) == (None, None)
