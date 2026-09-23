"""RED-phase tests for `app/db.py` (P2 of
odd/tasks/datev-mock-write-endpoints-and-observability.md): the generic
SQLite-backed CRUD core behind every new write endpoint.

`app/db.py` does not exist yet; this file is expected to fail on collection
with `ModuleNotFoundError` until the GREEN-phase implementation lands.

## Test isolation

`app.db.DB_PATH` is monkeypatched to a fresh `tmp_path` file per test (same
precedent as `app.config.SETTINGS_PATH` in `tests/test_admin_api.py`) via
the session-wide autouse fixture in `tests/conftest.py` -- every test in the
whole suite gets an isolated SQLite file, never the real project-root
`datev_mock.db`. This file's own fixture just calls `db.reset()` again for
extra safety/clarity at the point of use, matching this project's existing
`data_store.reset()` fixture idiom (`tests/test_data_store.py`).

Contract under test (settled here, for the GREEN implementer):
  - `init_db()` creates the `stored_records` table if it doesn't exist yet;
    safe to call repeatedly.
  - `upsert_record(resource_type, record_id, data, client_id=None,
    fiscal_year_id=None)` inserts or replaces a row, keyed on
    `(resource_type, record_id)`.
  - `get_record(resource_type, record_id)` returns the stored `data` dict,
    or `None` if not found.
  - `list_records(resource_type, client_id=None, fiscal_year_id=None)`
    returns every stored `data` dict for that resource type (optionally
    filtered by client_id/fiscal_year_id when given).
  - `delete_record(resource_type, record_id)` removes the row and returns
    `True`, or `False` if nothing matched.
  - `reset()` deletes every row (all resource types) -- for test isolation.
  - A second `upsert_record` call for the same `(resource_type, record_id)`
    keeps the original `created_at` but changes `updated_at`.
"""
from __future__ import annotations

import time

import pytest

from app import db


@pytest.fixture(autouse=True)
def _reset_db():
    db.reset()
    yield
    db.reset()


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()  # must not raise on a second call


def test_upsert_then_get_record_round_trips():
    stored = db.upsert_record("accounting.debitors", "d1", {"id": "d1", "caption": "Acme"})
    assert stored["caption"] == "Acme"

    fetched = db.get_record("accounting.debitors", "d1")
    assert fetched == {"id": "d1", "caption": "Acme"}


def test_get_record_returns_none_when_missing():
    assert db.get_record("accounting.debitors", "does-not-exist") is None


def test_list_records_returns_every_row_for_a_resource_type():
    db.upsert_record("accounting.debitors", "d1", {"id": "d1", "caption": "Acme"})
    db.upsert_record("accounting.debitors", "d2", {"id": "d2", "caption": "Beta"})
    db.upsert_record("accounting.creditors", "c1", {"id": "c1", "caption": "Gamma"})

    debitors = db.list_records("accounting.debitors")
    assert {r["id"] for r in debitors} == {"d1", "d2"}

    creditors = db.list_records("accounting.creditors")
    assert {r["id"] for r in creditors} == {"c1"}


def test_delete_record_removes_it_and_reports_success():
    db.upsert_record("accounting.debitors", "d1", {"id": "d1", "caption": "Acme"})
    assert db.delete_record("accounting.debitors", "d1") is True
    assert db.get_record("accounting.debitors", "d1") is None


def test_delete_record_returns_false_for_unknown_id():
    assert db.delete_record("accounting.debitors", "does-not-exist") is False


def test_reset_clears_every_resource_type():
    db.upsert_record("accounting.debitors", "d1", {"id": "d1"})
    db.upsert_record("accounting.creditors", "c1", {"id": "c1"})
    db.reset()
    assert db.list_records("accounting.debitors") == []
    assert db.list_records("accounting.creditors") == []


def test_upsert_keeps_created_at_but_changes_updated_at_on_second_write():
    db.upsert_record("accounting.debitors", "d1", {"id": "d1", "caption": "Acme"})
    first = db._row_meta("accounting.debitors", "d1")  # internal helper, see app/db.py

    time.sleep(0.01)
    db.upsert_record("accounting.debitors", "d1", {"id": "d1", "caption": "Acme Updated"})
    second = db._row_meta("accounting.debitors", "d1")

    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] != first["updated_at"]
    assert db.get_record("accounting.debitors", "d1")["caption"] == "Acme Updated"


def test_list_records_filters_by_client_id_and_fiscal_year_id():
    db.upsert_record(
        "accounting.debitors", "d1", {"id": "d1"}, client_id="c-1", fiscal_year_id="fy-1"
    )
    db.upsert_record(
        "accounting.debitors", "d2", {"id": "d2"}, client_id="c-2", fiscal_year_id="fy-1"
    )

    filtered = db.list_records("accounting.debitors", client_id="c-1")
    assert {r["id"] for r in filtered} == {"d1"}


def test_list_all_with_meta_returns_metadata_for_admin_ui():
    db.upsert_record(
        "accounting.debitors", "d1", {"id": "d1", "caption": "Acme"}, client_id="c-1"
    )
    rows = db.list_all_with_meta()
    assert len(rows) == 1
    row = rows[0]
    assert row["resource_type"] == "accounting.debitors"
    assert row["record_id"] == "d1"
    assert row["client_id"] == "c-1"
    assert row["data"] == {"id": "d1", "caption": "Acme"}
    assert "created_at" in row and "updated_at" in row


def test_delete_records_bulk_removes_matching_rows_only():
    db.upsert_record(
        "master_data.client_responsibilities", "r1", {"id": 1}, client_id="client-a"
    )
    db.upsert_record(
        "master_data.client_responsibilities", "r2", {"id": 2}, client_id="client-a"
    )
    db.upsert_record(
        "master_data.client_responsibilities", "r3", {"id": 3}, client_id="client-b"
    )

    deleted = db.delete_records("master_data.client_responsibilities", client_id="client-a")

    assert deleted == 2
    remaining = db.list_records("master_data.client_responsibilities")
    assert {r["id"] for r in remaining} == {3}
