"""RED-phase tests for `app/config.py` — persisted settings with an
overridable file path.

`app/config.py` does not exist yet; this file is expected to fail on
collection with `ModuleNotFoundError` until S1 (GREEN phase) implements it.
See `odd/tasks/datev-mock-settings.md` for the planned contract this test
file is designing.

Contract under test (settled here, for the GREEN implementer):
  - `Settings` is a dataclass with `port: int = 58452` and
    `default_accounting_format: str = "xml"`.
  - Constructing an invalid `Settings` (bad port range, unknown format)
    raises `ValueError` immediately — validation lives on construction, not
    bolted on separately in `load_settings`/`save_settings`.
  - `SETTINGS_PATH` is a module-level `pathlib.Path` that `load_settings`/
    `save_settings` re-read from the module namespace on every call (not a
    value captured once at import time), so tests can
    `monkeypatch.setattr("app.config.SETTINGS_PATH", tmp_path / "...")` and
    be certain no real file under the repo is ever touched.
  - `load_settings()` returns `Settings()` defaults when `SETTINGS_PATH`
    does not exist — it must not raise just because no file was ever saved.
  - `save_settings(settings)` writes JSON to `SETTINGS_PATH` containing at
    least `port` and `default_accounting_format`.
"""
from __future__ import annotations

import json

import pytest

from app.config import Settings, load_settings, save_settings

DEFAULT_PORT = 58452
DEFAULT_FORMAT = "xml"


@pytest.fixture()
def settings_path(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("app.config.SETTINGS_PATH", path)
    return path


def test_settings_defaults_are_port_58452_and_format_xml():
    settings = Settings()
    assert settings.port == DEFAULT_PORT
    assert settings.default_accounting_format == DEFAULT_FORMAT


def test_load_settings_returns_defaults_when_no_file_exists(settings_path):
    assert not settings_path.exists()

    loaded = load_settings()

    assert loaded.port == DEFAULT_PORT
    assert loaded.default_accounting_format == DEFAULT_FORMAT


def test_save_then_load_round_trip(settings_path):
    save_settings(Settings(port=12345, default_accounting_format="json"))
    assert settings_path.exists()

    loaded = load_settings()

    assert loaded.port == 12345
    assert loaded.default_accounting_format == "json"


def test_save_settings_writes_json_to_the_overridden_path_only(settings_path, tmp_path):
    save_settings(Settings(port=9000, default_accounting_format="json"))

    # Nothing else was created next to it — in particular, no stray file at
    # the real project-root settings path (this fixture's tmp_path stands in
    # for that root, so "no sibling files" is the closest in-process proxy
    # for "we never touched the real settings file").
    other_files = [p for p in tmp_path.iterdir() if p != settings_path]
    assert other_files == []

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["port"] == 9000
    assert data["default_accounting_format"] == "json"


def test_invalid_default_accounting_format_is_rejected():
    with pytest.raises(ValueError):
        Settings(default_accounting_format="yaml")


def test_port_zero_is_rejected():
    with pytest.raises(ValueError):
        Settings(port=0)


def test_port_above_65535_is_rejected():
    with pytest.raises(ValueError):
        Settings(port=65536)


def test_port_negative_is_rejected():
    with pytest.raises(ValueError):
        Settings(port=-1)


def test_port_at_valid_boundaries_is_accepted():
    assert Settings(port=1).port == 1
    assert Settings(port=65535).port == 65535
