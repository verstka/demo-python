"""Application settings loaded from environment."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    verstka_api_key: str = Field(default="", validation_alias="VERSTKA_API_KEY")
    verstka_api_secret: str = Field(default="", validation_alias="VERSTKA_API_SECRET")
    verstka_callback_url: str = Field(default="", validation_alias="VERSTKA_CALLBACK_URL")
    verstka_api_url: str = Field(
        default="https://api.r2.verstka.org/integration",
        validation_alias="VERSTKA_API_URL",
    )

    public_base_url: str = Field(default="http://127.0.0.1:8000", validation_alias="PUBLIC_BASE_URL")
    session_secret: str = Field(default="dev-secret-change-me", validation_alias="SESSION_SECRET")
    database_url: str = Field(default="sqlite+aiosqlite:///./data.db", validation_alias="DATABASE_URL")

    # When true, logs each HTTP request/response (headers + body preview) to stdout — dev only.
    debug: bool = Field(default=False, validation_alias="DEBUG")

    # JSON string in .env: {"user":"$argon2id$..."}
    admins_json: str = Field(default="{}", validation_alias="ADMINS")

    storage_dir: Path = Field(default=Path("storage"))
    templates_dir: Path = Field(default=Path(__file__).resolve().parent / "templates")
    static_dir: Path = Field(default=Path(__file__).resolve().parent / "static")

    @field_validator("storage_dir", "templates_dir", "static_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v: Any) -> Path:
        return Path(v) if v is not None else Path(".")

    @field_validator("verstka_api_key", "verstka_api_secret", "verstka_callback_url", mode="before")
    @classmethod
    def _strip_verstka_strings(cls, v: Any) -> Any:
        """Avoid invalid_signature from accidental spaces/newlines in .env."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, int):
            return v != 0
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    def admins_seed(self) -> dict[str, str]:
        raw = (self.admins_json or "{}").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("ADMINS must be a JSON object")
        return {str(k): str(v) for k, v in data.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
