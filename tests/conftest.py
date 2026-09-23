"""Shared pytest fixtures for the DATEV mock API test suite.

RED phase: `app.main` does not exist yet. Importing it here is intentional —
collection is expected to fail (ModuleNotFoundError) until the GREEN-phase
implementation is written. That failure is the correct RED signal for this
step; do not add try/except around this import to hide it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app  # noqa: E402  (intentionally fails until app/ exists)


@pytest.fixture()
def client() -> TestClient:
    """A FastAPI TestClient bound to the mock app, one per test."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_sqlite_db(tmp_path_factory, monkeypatch):
    """Every test gets its own SQLite file, never the real project-root
    `datev_mock.db` (P2 of
    odd/tasks/datev-mock-write-endpoints-and-observability.md).

    Unlike `data_store.reset()` (only mutated by a couple of admin-focused
    test files, each with its own local fixture), `app.db` is now exercised
    by nearly every GET endpoint's test (Group A resources merge SQLite-
    stored records into their fake dataset on every read), so the safe
    default has to be session-wide and automatic rather than opt-in per
    file. `DB_PATH` is monkeypatched the same way `app.config.SETTINGS_PATH`
    already is in `tests/test_admin_api.py` -- a fresh `tmp_path` file, not
    `:memory:`, since `app.db` opens a short-lived connection per call and
    an in-memory SQLite database does not persist across separate
    connections.
    """
    # A dedicated pytest-managed temp directory via `tmp_path_factory`, not
    # the test's own `tmp_path` -- a couple of other test modules (e.g.
    # tests/test_config.py) assert "no stray sibling files/dirs" directly
    # against their own `tmp_path`, so a same-directory (or even nested
    # sub-directory) db file would collide with that unrelated assertion.
    db_dir = tmp_path_factory.mktemp("sqlite_db")
    monkeypatch.setattr(db, "DB_PATH", db_dir / "test_datev_mock.db")
    db.reset()
    yield
    db.reset()
