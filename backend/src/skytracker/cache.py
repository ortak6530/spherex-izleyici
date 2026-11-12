"""Tiny file cache. SPHEREx data lives under cache/<release>/, everything else under cache/_external/.

Values are JSON (with fetched_at) or raw bytes. Writes are atomic (temp file + rename).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from .settings import get_settings

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _root() -> Path:
    return get_settings().cache_path


def _path(namespace: str, key: str, ext: str) -> Path:
    # namespace is e.g. "qr2/cutouts" or "_external/sesame"; keys are hashed unless short and safe
    safe = _SAFE.sub("_", key)
    name = safe if len(safe) <= 80 and safe == key else hashlib.sha256(key.encode()).hexdigest()[:40]
    parts = [p for p in namespace.split("/") if p and p not in (".", "..")]
    return _root().joinpath(*parts, name + ext)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def get_json(namespace: str, key: str, ttl_s: float | None) -> dict | None:
    p = _path(namespace, key, ".json")
    try:
        if ttl_s is not None and time.time() - p.stat().st_mtime > ttl_s:
            return None
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def put_json(namespace: str, key: str, value: Any) -> None:
    _atomic_write(_path(namespace, key, ".json"), json.dumps(value, ensure_ascii=False).encode("utf-8"))


def get_bytes(namespace: str, key: str, ext: str = ".bin") -> bytes | None:
    try:
        return _path(namespace, key, ext).read_bytes()
    except OSError:
        return None


def put_bytes(namespace: str, key: str, data: bytes, ext: str = ".bin") -> Path:
    p = _path(namespace, key, ext)
    _atomic_write(p, data)
    return p


def cache_age_s(namespace: str, key: str, ext: str = ".json") -> float | None:
    try:
        return time.time() - _path(namespace, key, ext).stat().st_mtime
    except OSError:
        return None
