"""Per-pixel wavelength from the SPHEREx WCS-WAVE lookup table.

Faz 0 finding: astropy applies the celestial SIP distortion to the 'W' (wavelength) lookup WCS too,
shifting the wavelength by up to ~16 nm. The lookup table is defined in raw FITS pixel coordinates,
so SIP keywords are stripped before building the spectral WCS.
"""

from __future__ import annotations

import warnings

from astropy import log as astropy_log
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

astropy_log.setLevel("ERROR")

_SIP_PREFIXES = ("A_", "B_", "AP_", "BP_")


def strip_sip(header: fits.Header) -> fits.Header:
    h = header.copy()
    for k in list(h.keys()):
        if k.startswith(_SIP_PREFIXES):
            del h[k]
    return h


def wave_wcs(image_header: fits.Header, wcs_wave_hdu: fits.BinTableHDU) -> WCS:
    tbl = wcs_wave_hdu.copy()
    tbl.header["EXTNAME"] = "WCS-WAVE"
    h = strip_sip(image_header)
    hdul = fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(header=h), tbl])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(h, fobj=hdul, key="W")


def celestial_wcs(image_header: fits.Header) -> WCS:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(image_header)


def wavelength_at(image_header: fits.Header, wcs_wave_hdu: fits.BinTableHDU, x: float, y: float):
    """(wavelength_um, bandwidth_um) at 0-based pixel (x, y)."""
    lam, bw = wave_wcs(image_header, wcs_wave_hdu).pixel_to_world_values(x, y)
    return float(lam), float(bw)
