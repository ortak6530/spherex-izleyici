"""Coordinate parser for the search bar (pure; no network).

Accepted forms (ICRS unless galactic):
  decimal degrees      10.684 41.269 | 10.684, +41.269 | 10.684d 41.269d
                       10,684 41,269 (Turkish decimal comma)
  hours/degrees        00h42m44s +41d16m09s | 0h42m44.3s 41°16'09"
  colon separated      00:42:44.3 +41:16:09
  space separated      00 42 44.3 +41 16 09
  galactic             l=121.17 b=-21.57 | l=121.17, b=-21.57
Returns None when the text does not look like coordinates (then it is treated as a name).
Raises CoordinateError for text that looks like coordinates but is out of range.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


class CoordinateError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ParsedCoord:
    ra: float  # degrees, ICRS
    dec: float  # degrees, ICRS
    input_format: str  # decimal | sexagesimal | galactic
    galactic: tuple[float, float] | None = None


_NUM = r"[-+]?\d+(?:\.\d+)?"
_GAL = re.compile(rf"^\s*l\s*=\s*({_NUM})\s*[,;\s]\s*b\s*=\s*({_NUM})\s*$", re.I)
_DEC2 = re.compile(rf"^\s*({_NUM})\s*(?:d|°|deg)?\s*[,;\s]\s*({_NUM})\s*(?:d|°|deg)?\s*$", re.I)
_TR_COMMA = re.compile(r"^\s*([-+]?\d+,\d+)\s+([-+]?\d+,\d+)\s*$")
# 00h42m44.3s +41d16m09s  /  00h42m44s 41°16'09"
_HMS = re.compile(
    r"^\s*(\d{1,2})\s*h\s*(\d{1,2})\s*m\s*(\d{1,2}(?:\.\d+)?)\s*s?\s*[,;\s]\s*"
    r"([-+]?)\s*(\d{1,2})\s*(?:d|°)\s*(\d{1,2})\s*(?:m|'|′)\s*(\d{1,2}(?:\.\d+)?)\s*(?:s|\"|″)?\s*$",
    re.I,
)
# 00:42:44.3 +41:16:09   or   00 42 44.3 +41 16 09
_COLON = re.compile(
    r"^\s*(\d{1,2})[:\s](\d{1,2})[:\s](\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*"
    r"([-+]?)(\d{1,2})[:\s](\d{1,2})[:\s](\d{1,2}(?:\.\d+)?)\s*$"
)


def _check(ra: float, dec: float) -> None:
    if not (math.isfinite(ra) and math.isfinite(dec)):
        raise CoordinateError("INVALID_COORDINATE")
    if not 0.0 <= ra < 360.0:
        raise CoordinateError("RA_OUT_OF_RANGE")
    if not -90.0 <= dec <= 90.0:
        raise CoordinateError("DEC_OUT_OF_RANGE")


def _sexagesimal(m: re.Match[str]) -> tuple[float, float]:
    h, mi, s, sign, d, dm, ds = m.groups()
    h_, mi_, s_, d_, dm_, ds_ = int(h), int(mi), float(s), int(d), int(dm), float(ds)
    if h_ >= 24 or mi_ >= 60 or s_ >= 60:
        raise CoordinateError("RA_OUT_OF_RANGE")
    if dm_ >= 60 or ds_ >= 60 or d_ > 90:
        raise CoordinateError("DEC_OUT_OF_RANGE")
    ra = 15.0 * (h_ + mi_ / 60.0 + s_ / 3600.0)
    dec = d_ + dm_ / 60.0 + ds_ / 3600.0
    if sign == "-":
        dec = -dec
    return ra, dec


def galactic_to_icrs(l_deg: float, b_deg: float) -> tuple[float, float]:
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    c = SkyCoord(l=l_deg * u.deg, b=b_deg * u.deg, frame="galactic").icrs
    return float(c.ra.deg) % 360.0, float(c.dec.deg)


def parse_coordinates(text: str) -> ParsedCoord | None:
    s = (text or "").strip()
    if not s or len(s) > 100:
        return None

    if m := _GAL.match(s):
        l_deg, b_deg = float(m.group(1)), float(m.group(2))
        if not -90.0 <= b_deg <= 90.0:
            raise CoordinateError("DEC_OUT_OF_RANGE")
        ra, dec = galactic_to_icrs(l_deg % 360.0, b_deg)
        return ParsedCoord(ra, dec, "galactic", (l_deg % 360.0, b_deg))

    if m := _HMS.match(s) or _COLON.match(s):
        ra, dec = _sexagesimal(m)
        _check(ra, dec)
        return ParsedCoord(ra, dec, "sexagesimal")

    if m := _TR_COMMA.match(s):
        ra, dec = (float(g.replace(",", ".")) for g in m.groups())
        _check(ra, dec)
        return ParsedCoord(ra, dec, "decimal")

    if m := _DEC2.match(s):
        ra, dec = float(m.group(1)), float(m.group(2))
        _check(ra, dec)
        return ParsedCoord(ra, dec, "decimal")

    return None
