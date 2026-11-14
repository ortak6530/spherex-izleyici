import os
import tempfile
from pathlib import Path

import pytest

# Isolated SQLite DB per test session; must be set before skytracker modules read settings
_tmp = Path(tempfile.mkdtemp(prefix="skytracker-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["APP_ENV"] = "development"
os.environ["IP_HASH_SALT"] = "test-salt"
os.environ["ARCHIVE_FRESHNESS_CHECK"] = "false"  # no live IRSA TAP query from the test app


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from skytracker.db import (
        Base,
        get_engine,
        models,  # noqa: F401
    )
    from skytracker.main import create_app

    Base.metadata.create_all(get_engine())
    with TestClient(create_app()) as c:
        yield c
