"""SQLite-backed persistence for every write ("POST"/"PUT") endpoint added
in P2 of `odd/tasks/datev-mock-write-endpoints-and-observability.md`.

Architecture decisions #1/#2 (see that doc): stdlib `sqlite3`, no new
dependency; one generic table for every resource family instead of a
bespoke schema per resource, matching this project's "match the shape,
don't over-engineer relational integrity" philosophy already established by
`app/data_store.py`.

**Connection handling**: a short-lived connection is opened and closed on
every call (`_connect()`), rather than one shared module-level connection
guarded by a `threading.Lock`. Chosen over the lock-based alternative
because it's simpler (no lock object to thread through every function, no
risk of a held connection leaking across requests) and this mock's own
traffic volume (manual/integration testing, not production load) makes the
extra per-call `sqlite3.connect()` cost irrelevant. Each connection uses
`isolation_level=None` (autocommit) so a single-statement write is durable
the moment its call returns, with no explicit `BEGIN`/`COMMIT` bookkeeping
needed for the simple single-row upserts this module performs.

`DB_PATH` is a module-level `Path` (never captured in a default argument or
closure), looked up fresh on every call -- same pattern as
`app.config.SETTINGS_PATH` -- so tests can monkeypatch it to an isolated
per-test file (see `tests/conftest.py::_isolated_sqlite_db`).
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.runtime_paths import base_dir

# Real project-root database file (git-ignored, runtime local state; see
# `.gitignore`). Tests override this at the module level so the real file is
# never touched -- same precedent as `app.config.SETTINGS_PATH`.
DB_PATH: Path = base_dir() / "datev_mock.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stored_records (
    resource_type TEXT NOT NULL,
    record_id     TEXT NOT NULL,
    client_id     TEXT,
    fiscal_year_id TEXT,
    data_json     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (resource_type, record_id)
);
"""


def _connect() -> sqlite3.Connection:
    """Open a short-lived connection against the *current* `DB_PATH`,
    ensuring the schema exists. Cheap enough to run `CREATE TABLE IF NOT
    EXISTS` on every call for a mock's traffic volume, and it guarantees the
    table exists no matter when `DB_PATH` was last monkeypatched (tests
    swap it before the app has a chance to run its own startup `init_db()`)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
    conn.execute(_CREATE_TABLE_SQL)
    return conn


def init_db() -> None:
    """Create the `stored_records` table if it doesn't exist yet. Safe to
    call repeatedly (e.g. once at app startup, from `app/main.py`'s
    lifespan) -- `_connect()` already runs the same `CREATE TABLE IF NOT
    EXISTS`, so this is mostly a documented, explicit entry point."""
    _connect().close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_record(
    resource_type: str,
    record_id: str,
    data: dict[str, Any],
    client_id: Optional[str] = None,
    fiscal_year_id: Optional[str] = None,
) -> dict[str, Any]:
    """Insert or replace the row for `(resource_type, record_id)`.
    `created_at` is preserved across an update (only set on first insert);
    `updated_at` always reflects this call. Returns `data` unchanged (the
    caller already has it; returned for convenient chaining, e.g. `return
    db.upsert_record(...)` directly from a router)."""
    now = _now()
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT created_at FROM stored_records WHERE resource_type = ? AND record_id = ?",
            (resource_type, record_id),
        ).fetchone()
        created_at = existing[0] if existing is not None else now
        conn.execute(
            """
            INSERT OR REPLACE INTO stored_records
                (resource_type, record_id, client_id, fiscal_year_id, data_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (resource_type, record_id, client_id, fiscal_year_id, json.dumps(data), created_at, now),
        )
    finally:
        conn.close()
    return data


def get_record(resource_type: str, record_id: str) -> Optional[dict[str, Any]]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data_json FROM stored_records WHERE resource_type = ? AND record_id = ?",
            (resource_type, record_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return json.loads(row[0])


def list_records(
    resource_type: str,
    client_id: Optional[str] = None,
    fiscal_year_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    query = "SELECT data_json FROM stored_records WHERE resource_type = ?"
    params: list[Any] = [resource_type]
    if client_id is not None:
        query += " AND client_id = ?"
        params.append(client_id)
    if fiscal_year_id is not None:
        query += " AND fiscal_year_id = ?"
        params.append(fiscal_year_id)

    conn = _connect()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [json.loads(row[0]) for row in rows]


def delete_record(resource_type: str, record_id: str) -> bool:
    conn = _connect()
    try:
        cursor = conn.execute(
            "DELETE FROM stored_records WHERE resource_type = ? AND record_id = ?",
            (resource_type, record_id),
        )
        deleted = cursor.rowcount > 0
    finally:
        conn.close()
    return deleted


def delete_records(
    resource_type: str,
    client_id: Optional[str] = None,
    fiscal_year_id: Optional[str] = None,
) -> int:
    """Bulk counterpart to `list_records()`/`delete_record()`: delete every
    row matching the given filters, returning the number of rows removed.
    Used by "replace the whole list" write endpoints (e.g. `PUT
    .../clients/{id}/responsibilities`) to clear prior state before storing
    the newly-submitted list, without the caller needing to first look up
    each row's own `record_id`."""
    query = "DELETE FROM stored_records WHERE resource_type = ?"
    params: list[Any] = [resource_type]
    if client_id is not None:
        query += " AND client_id = ?"
        params.append(client_id)
    if fiscal_year_id is not None:
        query += " AND fiscal_year_id = ?"
        params.append(fiscal_year_id)

    conn = _connect()
    try:
        cursor = conn.execute(query, params)
        deleted = cursor.rowcount
    finally:
        conn.close()
    return deleted


def reset() -> None:
    """Delete every row, across every resource type -- for test isolation
    (mirrors `app.data_store.reset()`) and the admin UI's "reset all data"
    action, if ever wired up to also clear stored writes."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM stored_records")
    finally:
        conn.close()


def list_all_with_meta() -> list[dict[str, Any]]:
    """Every stored row, across every resource type, with its metadata --
    for the admin UI's "Stored records" card (architecture decision #8).
    Not part of the 6 functions architecture decision #2 named explicitly,
    but the same "generic, resource-type-agnostic" spirit: the admin UI
    needs to show *all* written records grouped by resource type, and a
    single query here avoids the router hardcoding a list of resource-type
    strings just to fan out `list_records()` calls."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT resource_type, record_id, client_id, fiscal_year_id, data_json, "
            "created_at, updated_at FROM stored_records ORDER BY resource_type, record_id"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "resource_type": resource_type,
            "record_id": record_id,
            "client_id": client_id,
            "fiscal_year_id": fiscal_year_id,
            "data": json.loads(data_json),
            "created_at": created_at,
            "updated_at": updated_at,
        }
        for resource_type, record_id, client_id, fiscal_year_id, data_json, created_at, updated_at in rows
    ]


def _row_meta(resource_type: str, record_id: str) -> Optional[dict[str, str]]:
    """Test/internal helper: `created_at`/`updated_at` for one row, without
    the `data_json` payload. Used by `tests/test_db.py` to assert the
    "created_at survives, updated_at changes" upsert contract without
    reaching into SQL directly."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT created_at, updated_at FROM stored_records WHERE resource_type = ? AND record_id = ?",
            (resource_type, record_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {"created_at": row[0], "updated_at": row[1]}


# --- GET-merges-SQLite helper (architecture decision #4) ---
#
# Not one of the 6 CRUD functions architecture decision #2 names explicitly,
# but lives here rather than duplicated per-router: every Group A GET
# handler needs the exact same "union the fake dataset with SQLite-stored
# records, SQLite wins on a shared id" logic, and this is the one place that
# already understands both the generic row format and dataclass
# introspection needed to turn a stored dict back into the dataclass
# instance the existing XML/JSON serializers expect.


def _default_for_annotation(type_str: Optional[str]) -> Any:
    """A safe default for a *required* dataclass field the stored dict
    doesn't have a value for (e.g. a partial write via the spec's own
    "every field is optional, PATCH-style" convention -- see Appendix A).
    Every required field across the 7 Group A resources is `str`/`int`/
    `bool` (confirmed by reading `app/models.py` directly), so this only
    needs to cover those three plus a safe fallback."""
    if type_str == "str":
        return ""
    if type_str == "int":
        return 0
    if type_str == "float":
        return 0.0
    if type_str == "bool":
        return False
    return None


def record_to_dataclass(
    dataclass_type: type,
    data: dict[str, Any],
    field_map: Optional[dict[str, str]] = None,
    nil_fields: frozenset[str] = frozenset(),
) -> Any:
    """Build a `dataclass_type` instance from a stored (validated,
    snake_case) record dict.

    - `field_map` translates a stored snake_case key to the dataclass's own
      field name when they differ (only `ClientResource` needs this -- its
      fields are PascalCase, matching the real XML element names, while
      every other Group A dataclass already uses snake_case 1:1 with its
      Pydantic write model).
    - Keys in `data` with no matching dataclass field are silently dropped
      (e.g. `Addressee`'s write-only `detail`/`addresses`/`communications`/
      `bank_accounts`/`tax_offices`/`contact_persons` -- not modeled on the
      read-side dataclass at all, consistent with this mock's "no `expand`
      support" GET precedent: those fields simply don't appear on a
      default, non-expand response, same as they wouldn't for a
      fake-generated record).
    - `nil_fields` force specific fields to `None` regardless of what's
      stored -- used only for `Creditor`/`Debitor`'s
      `natural_person`/`legal_person`/`not_specified_person`/`addresses`/
      `banks`/`communications`/`accounting_information`: those are nested
      object/array fields with no dedicated XML sub-rendering (real
      DATEV evidence: never populated in the default, non-expand response
      either -- see `app/models.py::Creditor`'s docstring), so a raw dict a
      caller POSTed would otherwise render as a broken Python `repr()`
      inside `<NaturalPerson>...</NaturalPerson>`-shaped XML. Full fidelity
      of whatever was actually written stays visible in the admin UI's
      "Stored records" card (reads `db.list_all_with_meta()` directly, not
      through this function) and in the raw JSON any caller wrote.
    - Any dataclass field missing from `data` uses the field's own default
      when it has one, else a type-appropriate empty value (`""`/`0`/
      `False`) via `_default_for_annotation` -- every Group A required
      field is one of those three primitive types.
    """
    field_map = field_map or {}
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(dataclass_type):
        if f.name in nil_fields:
            kwargs[f.name] = None
            continue
        source_key = next((k for k, v in field_map.items() if v == f.name), f.name)
        if source_key in data:
            kwargs[f.name] = data[source_key]
        elif f.default is not dataclasses.MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            kwargs[f.name] = f.default_factory()  # type: ignore[misc]
        else:
            kwargs[f.name] = _default_for_annotation(f.type if isinstance(f.type, str) else None)
    return dataclass_type(**kwargs)


def merge_with_stored(
    fake_records: list[Any],
    resource_type: str,
    dataclass_type: type,
    id_field: str = "id",
    field_map: Optional[dict[str, str]] = None,
    nil_fields: frozenset[str] = frozenset(),
) -> list[Any]:
    """Union `fake_records` (dataclass instances from `app.fake_data`) with
    every SQLite-stored record for `resource_type`. A stored record whose id
    matches a fake one *replaces* it (PUT-over-fake semantics); a stored
    record with a new id is appended. `id_field` is the dataclass attribute
    name holding the id (`"id"` for every Group A resource except
    `ClientResource`, which uses `"Id"`)."""
    stored = list_records(resource_type)
    stored_instances = {
        getattr(instance, id_field): instance
        for instance in (
            record_to_dataclass(dataclass_type, row, field_map=field_map, nil_fields=nil_fields)
            for row in stored
        )
    }
    merged = [r for r in fake_records if getattr(r, id_field) not in stored_instances]
    merged.extend(stored_instances.values())
    return merged
