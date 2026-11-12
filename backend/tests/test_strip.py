from skytracker.api.v1.compare import strip_arrays
from skytracker.services.object_compare import _ab_mag


def test_strip_arrays_removes_nested_pixel_data():
    r = {"id": "x", "a_b64": "AAAA", "a_view": {"data_b64": "BBBB", "ab_mag": 9.1}, "n": 3}
    assert strip_arrays(r) == {"id": "x", "a_view": {"ab_mag": 9.1}, "n": 3}


def test_ab_magnitude():
    assert _ab_mag(3631e6) == 0.0  # 3631 Jy -> AB 0
    assert abs(_ab_mag(36.31) - 20.0) < 1e-9  # 36.31 µJy -> AB 20
    assert _ab_mag(-5.0) is None and _ab_mag(None) is None
