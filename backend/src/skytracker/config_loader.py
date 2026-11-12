"""Loads the TOML configuration in /config (releases, upstream allowlist, demo targets)."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .settings import get_settings

ReleaseStatus = Literal["active", "staged", "superseded", "retired"]


class Supersedes(BaseModel):
    release: str
    start: str
    end: str


class Release(BaseModel):
    id: str
    label: str
    status: ReleaseStatus
    announced: bool = True  # False -> UI shows `notice` ("official announcement pending")
    notice: str = ""
    calib_family: str
    sia_collections: list[str] = Field(default_factory=list)
    deep_collections: list[str] = Field(default_factory=list)
    ibe_prefix: str = ""
    s3_prefix: str = ""
    doi: str = ""
    flags_header_style: Literal["auto", "MP", "MSK"] = "auto"
    cross_family_correction: str | None = None
    flux_corrections_url: str | None = None
    show_with_warning: bool = False
    supersedes: Supersedes | None = None
    notes: str = ""


class ReleaseConfig(BaseModel):
    default_release: str
    release: list[Release]

    @model_validator(mode="after")
    def _check(self) -> ReleaseConfig:
        ids = [r.id for r in self.release]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate release id in releases.toml")
        if self.default_release not in ids:
            raise ValueError(f"default_release '{self.default_release}' is not defined")
        default = next(r for r in self.release if r.id == self.default_release)
        if default.status != "active":
            raise ValueError("default_release must have status 'active'")
        for r in self.release:
            if r.supersedes and r.supersedes.release not in ids:
                raise ValueError(f"release '{r.id}' supersedes unknown release '{r.supersedes.release}'")
        return self

    @property
    def active(self) -> list[Release]:
        return [r for r in self.release if r.status == "active"]

    def get(self, release_id: str) -> Release | None:
        return next((r for r in self.release if r.id == release_id), None)


class UpstreamGroup(BaseModel, extra="allow"):
    hosts: list[str]
    timeout: float = 30
    concurrency: int = 4


class UpstreamConfig(BaseModel):
    groups: dict[str, UpstreamGroup]

    @property
    def allowed_hosts(self) -> set[str]:
        return {h.lower() for g in self.groups.values() for h in g.hosts}

    def group_for_host(self, host: str) -> str | None:
        host = host.lower()
        return next((name for name, g in self.groups.items() if host in g.hosts), None)


class DemoTarget(BaseModel):
    key: str
    query: str
    label: str
    kind: Literal["object", "solar_system"] = "object"


class DemoTargets(BaseModel):
    target: list[DemoTarget]


def _read(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


@lru_cache
def releases() -> ReleaseConfig:
    return ReleaseConfig.model_validate(_read(get_settings().config_dir / "releases.toml"))


@lru_cache
def upstreams() -> UpstreamConfig:
    return UpstreamConfig.model_validate(_read(get_settings().config_dir / "upstreams.toml"))


@lru_cache
def demo_targets() -> DemoTargets:
    return DemoTargets.model_validate(_read(get_settings().config_dir / "demo_targets.toml"))


@lru_cache
def attributions() -> dict:
    return _read(get_settings().config_dir / "attributions.toml")
