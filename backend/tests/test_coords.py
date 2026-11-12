import pytest

from skytracker.domain.coords import CoordinateError, parse_coordinates

M31 = (10.684708, 41.26875)


def close(p, ra, dec, tol=2e-3):
    return abs(p.ra - ra) < tol and abs(p.dec - dec) < tol


@pytest.mark.parametrize(
    "text",
    [
        "10.684708 41.26875",
        "10.684708, 41.26875",
        "10.684708d +41.26875d",
        "10,684708 41,26875",
        "00h42m44.33s +41d16m07.5s",
        "0h42m44.33s 41°16'07.5\"",
        "00:42:44.33 +41:16:07.5",
        "00 42 44.33 +41 16 07.5",
    ],
)
def test_m31_in_all_formats(text):
    p = parse_coordinates(text)
    assert p is not None and close(p, *M31), text


def test_galactic_m31():
    # M31 is at l=121.17, b=-21.57
    p = parse_coordinates("l=121.1743 b=-21.5733")
    assert p.input_format == "galactic" and close(p, *M31, tol=1e-2)


def test_negative_declination():
    p = parse_coordinates("05:35:17.3 -05:23:28")  # M42
    assert abs(p.dec - (-5.391)) < 1e-3


@pytest.mark.parametrize("name", ["M31", "Betelgeuse", "WISE 0855", "NGC 224", "3I/ATLAS", "C/2025 N1", ""])
def test_names_are_not_coordinates(name):
    assert parse_coordinates(name) is None


@pytest.mark.parametrize(
    "text,code",
    [
        ("400 10", "RA_OUT_OF_RANGE"),
        ("10 95", "DEC_OUT_OF_RANGE"),
        ("25h00m00s +10d00m00s", "RA_OUT_OF_RANGE"),
        ("10:61:00 +10:00:00", "RA_OUT_OF_RANGE"),
        ("l=10 b=120", "DEC_OUT_OF_RANGE"),
    ],
)
def test_out_of_range(text, code):
    with pytest.raises(CoordinateError) as e:
        parse_coordinates(text)
    assert e.value.code == code
