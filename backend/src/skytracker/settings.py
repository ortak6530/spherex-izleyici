"""Application settings, read from environment variables and the repo-root .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/skytracker/settings.py -> repo root is three levels above the package directory
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: str = "development"
    public_base_url: str = "http://localhost:8000"
    secret_key: str = ""
    ip_hash_salt: str = ""
    allowed_origins: str = "http://localhost:5173"

    database_url: str = "sqlite:///./data/app.db"
    cache_dir: str = "./data/cache"
    cache_max_gb: float = 5.0
    event_retention_days: int = 90

    admin_email: str = ""

    emailjs_service_id: str = ""
    emailjs_template_id: str = ""
    emailjs_public_key: str = ""
    emailjs_private_key: str = ""

    wikimedia_user_agent: str = "SPHEREx-Gokyuzu-Izleyici/0.1"
    # Background check of the archive's newest SPHEREx observation (IRSA TAP, ~2 min per query)
    archive_freshness_check: bool = True

    config_dir: Path = Field(default=REPO_ROOT / "config")
    frontend_dist: Path = Field(default=REPO_ROOT / "frontend" / "dist")

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Render gives postgres://...; SQLAlchemy + psycopg 3 needs postgresql+psycopg://
        if v.startswith("postgres://"):
            v = "postgresql+psycopg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        elif v.startswith("sqlite:///./"):
            v = "sqlite:///" + (REPO_ROOT / v[len("sqlite:///./") :]).as_posix()
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cache_path(self) -> Path:
        p = Path(self.cache_dir)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
