import pytest
from pydantic import ValidationError

from skytracker.config_loader import ReleaseConfig, releases, upstreams
from skytracker.security import ip_hash, ua_family
from skytracker.settings import Settings


def test_release_config_loads():
    cfg = releases()
    assert {r.id for r in cfg.active} == {"dr1", "qr3"}  # QR2 superseded on 2026-11-12
    assert cfg.get("dr1").supersedes.release == "qr2"


def test_new_release_is_config_only():
    """Adding a release is just another block; validation catches mistakes."""
    base = {
        "default_release": "qr2",
        "release": [
            {"id": "qr2", "label": "QR2", "status": "active", "calib_family": "R6"},
            {
                "id": "qr4",
                "label": "QR4",
                "status": "active",
                "calib_family": "R8",
                "sia_collections": ["spherex_qr4"],
            },
        ],
    }
    assert len(ReleaseConfig.model_validate(base).active) == 2
    bad = {**base, "default_release": "nope"}
    with pytest.raises(ValidationError):
        ReleaseConfig.model_validate(bad)


def test_upstream_allowlist():
    up = upstreams()
    assert "irsa.ipac.caltech.edu" in up.allowed_hosts
    assert "vizier.idia.ac.za" in up.allowed_hosts  # Sesame redirect target
    assert "example.com" not in up.allowed_hosts
    assert up.group_for_host("simbad.cfa.harvard.edu") == "cds"


def test_render_postgres_url_is_normalised():
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_ip_hash_is_salted_and_not_reversible():
    h1, h2 = ip_hash("203.0.113.7"), ip_hash("203.0.113.8")
    assert h1 != h2 and len(h1) == 32 and "203" not in h1


def test_ua_family():
    assert ua_family("Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36") == "chrome"
    assert ua_family("Mozilla/5.0 (iPhone) Version/18 Mobile Safari/604.1") == "safari-mobile"
    assert ua_family(None) == "unknown"
