"""Persisted settings for the DATEV mock (port, default accounting format).

`SETTINGS_PATH` is a module-level attribute (never captured in a default
argument or a closure) so tests can override it with
`monkeypatch.setattr("app.config.SETTINGS_PATH", ...)`. `load_settings()` and
`save_settings()` look the name up from the module namespace on every call,
so a monkeypatched path takes effect immediately.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.runtime_paths import base_dir

_VALID_FORMATS = {"xml", "json"}


@dataclass
class Settings:
    """Persisted mock settings. Validated on construction."""

    port: int = 58452
    default_accounting_format: str = "xml"

    def __post_init__(self) -> None:
        if not (1 <= self.port <= 65535):
            raise ValueError(f"port must be between 1 and 65535, got {self.port!r}")
        if self.default_accounting_format not in _VALID_FORMATS:
            raise ValueError(
                "default_accounting_format must be one of "
                f"{sorted(_VALID_FORMATS)}, got {self.default_accounting_format!r}"
            )


# Real project-root settings file (git-ignored, runtime local state). Tests
# override this at the module level so the real file is never touched.
SETTINGS_PATH: Path = base_dir() / "settings.json"


def load_settings() -> Settings:
    """Load settings from `SETTINGS_PATH`, or return defaults when absent."""
    if not SETTINGS_PATH.exists():
        return Settings()

    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    return Settings(
        port=data.get("port", 58452),
        default_accounting_format=data.get("default_accounting_format", "xml"),
    )


def save_settings(settings: Settings) -> None:
    """Persist `settings` as JSON to `SETTINGS_PATH`."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(asdict(settings)), encoding="utf-8")
