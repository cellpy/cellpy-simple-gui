"""Application settings and paths."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CSG_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8577
    # Per-launch token guarding the local API against other processes on the box.
    token: str = secrets.token_urlsafe(16)
    app_name: str = "cellpy simple GUI"
    open_browser: bool = True  # used by the plain-server entry point

    @property
    def data_dir(self) -> Path:
        d = Path.home() / ".cellpy_simple_gui"
        d.mkdir(parents=True, exist_ok=True)
        return d


@lru_cache
def get_settings() -> Settings:
    return Settings()
