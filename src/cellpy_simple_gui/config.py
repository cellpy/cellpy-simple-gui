"""Application settings and paths."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Files one glob / load may pull in. The low default keeps a stray ``*`` from
#: dragging a whole archive into the library; dev mode is for stress-testing.
DEFAULT_MAX_FILES = 10
DEV_MAX_FILES = 500


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CSG_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8577
    # Per-launch token guarding the local API against other processes on the box.
    token: str = secrets.token_urlsafe(16)
    app_name: str = "cellpy simple GUI"
    open_browser: bool = True  # used by the plain-server entry point

    #: Unlock everything we deliberately hide from regular users (#97): every
    #: cellpy plot family rather than the curated set, and the higher batch
    #: limits. Off by default and not reachable from the UI — set
    #: ``CSG_DEV_MODE=1`` or pass ``--dev``.
    dev_mode: bool = False

    @property
    def data_dir(self) -> Path:
        d = Path.home() / ".cellpy_simple_gui"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def max_files(self) -> int:
        """Cap on files pulled in by one glob / load (raised in dev mode)."""
        return DEV_MAX_FILES if self.dev_mode else DEFAULT_MAX_FILES


@lru_cache
def get_settings() -> Settings:
    return Settings()
