"""SPHEREx FLAGS bit definitions, read from each file's own header.

QR2 headers use  MP_<NAME> = <bit>; R7 (QR3/DR1) headers use MSKNnnnn = <NAME> (bit nnnn).
Masks are defined by *names* (Explanatory Supplement v2.0, sec. 3.3), never by hard-coded bits.
"""

from __future__ import annotations

import re

import numpy as np

# Supplement sec. 3.3 "Flags for masking pixels for photometry calculations"
PHOTOMETRY_MASK = (
    "SUR_ERROR",
    "NONFUNC",
    "MISSING_DATA",
    "HOT",
    "COLD",
    "NONLINEAR",
    "PERSIST",
    "BLOOM",
    "SNOWBALL",
    "HALO",
    "SATELLITE_HALO",
)
# Supplement sec. 3.3 "Flags for background estimation masking"
BACKGROUND_MASK = PHOTOMETRY_MASK + ("OVERFLOW", "OUTLIER", "SOURCE", "TRANSIENT")
# Supplement sec. 3.4.3: pixels the IRSA mosaic tool treats as bad (used for display/difference images)
DISPLAY_MASK = (
    "TRANSIENT",
    "SUR_ERROR",
    "NONFUNC",
    "DICHROIC",
    "MISSING_DATA",
    "HOT",
    "COLD",
    "PHANMISS",
    "NONLINEAR",
    "PERSIST",
    "CROSSTALK",
    "GHOST",
    "GHOST_FPA",
    "GHOST_EXT",
    "STREAK",
    "BLOOM",
    "SNOWBALL",
    "HALO",
    "SATELLITE_HALO",
)

_MSKN = re.compile(r"^MSKN(\d{4})$")


def flag_schema(header) -> dict[str, int]:
    """{flag name: bit number} from a FLAGS extension header (either convention)."""
    schema: dict[str, int] = {}
    for key in header:
        if key.startswith("MP_"):
            try:
                schema[key[3:]] = int(header[key])
            except (TypeError, ValueError):
                continue
        elif m := _MSKN.match(key):
            schema[str(header[key]).strip()] = int(m.group(1))
    return schema


def mask_from(flags: np.ndarray, schema: dict[str, int], names: tuple[str, ...]) -> np.ndarray:
    bits = 0
    for n in names:
        if n in schema:
            bits |= 1 << schema[n]
    return (flags.astype(np.int64) & bits) != 0


def flag_fractions(flags: np.ndarray, schema: dict[str, int]) -> dict[str, float]:
    total = flags.size or 1
    out = {}
    for name, bit in schema.items():
        n = int(((flags.astype(np.int64) >> bit) & 1).sum())
        if n:
            out[name] = round(n / total, 4)
    return out
