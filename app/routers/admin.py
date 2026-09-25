"""Admin/settings UI and JSON API (`/admin`, `/admin/api/*`).

`GET /admin` serves a single self-contained HTML page (Bootstrap 5 via CDN,
vanilla JS, no build step, no frontend framework) that drives the JSON API
below via `fetch()`. See `odd/tasks/datev-mock-settings.md` for the
locked-in settings/CRUD contract and `odd/tasks/datev-mock-admin-ui-polish.md`
for the Bootstrap redesign + full endpoint catalog this page also serves.

The catalog section is purely presentational: it lists every mocked GET
endpoint (23 total) grouped by area and, for the 21 read-only extended
resources, fetches directly from their real public `/datev/api/...`
endpoints client-side on demand (no new backend routes). None of the JSON
API below (settings, master-data/accounting CRUD, reset) changed shape.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import config, data_store, db, overrides, request_log

router = APIRouter(tags=["admin"])

SETTINGS_ENDPOINT = "/admin/api/settings"
MASTER_DATA_ENDPOINT = "/admin/api/clients/master-data"
ACCOUNTING_ENDPOINT = "/admin/api/clients/accounting"
RESET_ENDPOINT = "/admin/api/reset"
STORED_RECORDS_ENDPOINT = "/admin/api/stored-records"
OVERRIDES_ENDPOINT = "/admin/api/overrides"
OVERRIDES_RESOLVE_ENDPOINT = "/admin/api/overrides/resolve"
LOGS_ENDPOINT = "/admin/api/logs"
LOGS_STREAM_ENDPOINT = "/admin/api/logs/stream"

# How long an idle SSE connection waits for a new log entry before sending a
# comment-only keep-alive frame (SSE clients/proxies otherwise time out an
# idle connection; a comment line is ignored by EventSource but keeps the
# connection alive).
_SSE_KEEPALIVE_SECONDS = 15.0


class SettingsPayload(BaseModel):
    port: int
    default_accounting_format: str
    datev_api_version: str = "legacy"


# --- settings ---


@router.get(SETTINGS_ENDPOINT)
def get_settings() -> dict:
    return asdict(config.load_settings())


@router.put(SETTINGS_ENDPOINT)
def put_settings(payload: SettingsPayload) -> dict:
    previous_port = config.load_settings().port

    try:
        new_settings = config.Settings(
            port=payload.port,
            default_accounting_format=payload.default_accounting_format,
            datev_api_version=payload.datev_api_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config.save_settings(new_settings)

    result = asdict(new_settings)
    result["restart_required"] = new_settings.port != previous_port
    return result


# --- master-data CRUD ---


@router.get(MASTER_DATA_ENDPOINT)
def get_master_data() -> list:
    return data_store.list_master_data()


@router.post(MASTER_DATA_ENDPOINT, status_code=201)
def post_master_data(fields: dict[str, Any]) -> Any:
    return data_store.add_master_data(fields)


@router.put(MASTER_DATA_ENDPOINT + "/{record_id}")
def put_master_data(record_id: str, fields: dict[str, Any]) -> Any:
    try:
        return data_store.update_master_data(record_id, fields)
    except KeyError:
        raise HTTPException(status_code=404, detail="master-data record not found")


@router.delete(MASTER_DATA_ENDPOINT + "/{record_id}")
def delete_master_data(record_id: str) -> dict:
    data_store.delete_master_data(record_id)
    return {"status": "ok"}


# --- accounting CRUD ---


@router.get(ACCOUNTING_ENDPOINT)
def get_accounting_clients_admin() -> list:
    return data_store.list_accounting_clients()


@router.post(ACCOUNTING_ENDPOINT, status_code=201)
def post_accounting_client(fields: dict[str, Any]) -> Any:
    return data_store.add_accounting_client(fields)


@router.put(ACCOUNTING_ENDPOINT + "/{record_id}")
def put_accounting_client(record_id: str, fields: dict[str, Any]) -> Any:
    try:
        return data_store.update_accounting_client(record_id, fields)
    except KeyError:
        raise HTTPException(status_code=404, detail="accounting client not found")


@router.delete(ACCOUNTING_ENDPOINT + "/{record_id}")
def delete_accounting_client(record_id: str) -> dict:
    data_store.delete_accounting_client(record_id)
    return {"status": "ok"}


# --- reset ---


@router.post(RESET_ENDPOINT)
def reset_data() -> dict:
    data_store.reset()
    return {"status": "ok"}


# --- stored records (SQLite-backed writes, P2 of
# datev-mock-write-endpoints-and-observability.md) ---


@router.get(STORED_RECORDS_ENDPOINT)
def get_stored_records() -> list[dict[str, Any]]:
    """Every record written via any of the 15 new write endpoints, across
    every resource type, read-only -- feeds the admin page's "Stored
    records" card. See `app.db.list_all_with_meta`."""
    return db.list_all_with_meta()


# --- live request/response log (see app/request_log.py) ---


@router.get(LOGS_ENDPOINT)
def get_logs() -> list[dict[str, Any]]:
    """Plain JSON snapshot of the ring buffer -- the primary way the admin
    page's "Live Request Log" card gets content on initial page load, and
    the endpoint this feature's automated tests exercise (SSE streaming
    itself is only smoke-tested; see `tests/test_request_log.py`)."""
    return request_log.get_backlog()


async def _sse_event_stream() -> AsyncIterator[str]:
    """Backlog first, then live entries as they're broadcast.

    Deliberately does NOT poll `request.is_disconnected()` -- that call
    deadlocks when the endpoint runs behind `app/request_log.py`'s own
    `BaseHTTPMiddleware`-based logging middleware (a documented Starlette
    incompatibility: `is_disconnected()`'s self-cancelling `CancelScope`
    trick conflicts with `call_next`'s own nested task group). Client
    disconnect is instead handled the standard way for an ASGI streaming
    generator: the server cancels this coroutine's task when the connection
    goes away, which surfaces here as `asyncio.CancelledError` propagating
    out of `queue.get()`/`wait_for()` -- the `finally` block below still
    runs and unregisters the subscriber queue either way.
    """
    for entry in request_log.get_backlog():
        yield f"data: {json.dumps(entry)}\n\n"

    queue = request_log.register_subscriber()
    try:
        while True:
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(entry)}\n\n"
    finally:
        request_log.unregister_subscriber(queue)


@router.get(LOGS_STREAM_ENDPOINT)
async def get_logs_stream() -> StreamingResponse:
    """Server-Sent-Events stream: the ring-buffer backlog first (so the
    browser has content immediately), then live entries as they're
    broadcast. SSE (not WebSocket) -- one-directional server->browser push
    only, plain HTTP, no new dependency."""
    return StreamingResponse(_sse_event_stream(), media_type="text/event-stream")


# --- custom overrides (upload/resolve/list/toggle/delete) ---
#
# See `odd/tasks/datev-mock-custom-overrides.md` for the locked-in contract.
# This is V1/V2-GREEN: the module + this admin API. Actually serving an
# active override from the public endpoint routers is a separate, later
# task (V3), not implemented here.


class ResolveOverridePayload(BaseModel):
    pending_id: str
    endpoint: str


class SetOverrideEnabledPayload(BaseModel):
    enabled: bool


@router.post(OVERRIDES_ENDPOINT)
async def post_override(file: UploadFile = File(...)) -> Any:
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(status_code=422, content={"status": "unrecognized"})

    # Real-world captured DATEV XML has been observed with bare, unescaped
    # "&" in text content (e.g. a company name with "&" in it) -- technically
    # invalid XML that the strict parser would otherwise reject outright.
    # Repair it before detecting/storing so both detection and whatever this
    # mock later serves are well-formed. No-op for JSON or already-valid XML.
    content = overrides.sanitize_xml(content)

    candidates = overrides.detect_candidates(content)
    if not candidates:
        return JSONResponse(status_code=422, content={"status": "unrecognized"})

    content_type = overrides.detect_content_type(content) or "json"
    filename = file.filename or "upload"

    if len(candidates) == 1:
        overrides.set_override(candidates[0], content, content_type, filename)
        return {"status": "matched", "endpoint": candidates[0]}

    pending_id = overrides.store_pending(content, content_type, filename, candidates)
    return {"status": "ambiguous", "candidates": candidates, "pending_id": pending_id}


@router.post(OVERRIDES_RESOLVE_ENDPOINT)
def post_resolve_override(payload: ResolveOverridePayload) -> dict:
    try:
        overrides.resolve_pending(payload.pending_id, payload.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get(OVERRIDES_ENDPOINT)
def get_overrides() -> dict:
    return overrides.list_overrides()


@router.put(OVERRIDES_ENDPOINT + "/{key}")
def put_override(key: str, payload: SetOverrideEnabledPayload) -> dict:
    overrides.set_enabled(key, payload.enabled)
    return {"status": "ok"}


@router.delete(OVERRIDES_ENDPOINT + "/{key}")
def delete_override(key: str) -> dict:
    overrides.delete_override(key)
    return {"status": "ok"}


# --- API catalog (presentational only; see module docstring) ---
#
# Every mocked GET endpoint, grouped by area, for the read-only "API
# Catalog" section of the admin page. `path` already has any path
# parameters resolved to obviously-illustrative example values
# (`example-client-id` etc.) since this mock ignores path-param values by
# design (see `odd/tasks/datev-mock-extended-endpoints.md`) — any value
# returns the same fixed dataset. `example_only` entries are shown as a
# path template without a live-fetch button (see task doc U2/"addressee by
# id" note).

_EXAMPLE_CLIENT = "example-client-id"
_EXAMPLE_FISCAL_YEAR = "example-fiscal-year-id"
_EXAMPLE_COST_SYSTEM = "example-cost-system-id"
_FY_PREFIX = f"/datev/api/accounting/v1/clients/{_EXAMPLE_CLIENT}/fiscal-years/{_EXAMPLE_FISCAL_YEAR}"

# NOTE (F1, odd/tasks/datev-mock-standalone-frontend.md): this list's *current
# values* are duplicated as a hand-baked JS literal in frontend/admin.html
# (the standalone admin page's embedded `CATALOG` constant). Editing this
# list does NOT automatically update frontend/admin.html — keep them in sync
# by hand (or regenerate frontend/admin.html) until/unless a later epic
# automates it.
CATALOG: list[dict[str, Any]] = [
    # Diagnostics
    {
        "area": "Diagnostics",
        "name": "Echo probe",
        "path": "/datev/api/diagnostics/v1/echo",
        "note": "Single XML object (not a list) — a diagnostics ping.",
    },
    # Base clients (already have CRUD tables above; listed here for reference)
    {
        "area": "Base clients",
        "name": "Master-data clients",
        "path": "/datev/api/master-data/v1/clients",
        "note": "XML. The CRUD table above uses the JSON admin endpoint "
        f"{MASTER_DATA_ENDPOINT}.",
    },
    {
        "area": "Base clients",
        "name": "Accounting clients",
        "path": "/datev/api/accounting/v1/clients",
        "note": "XML by default, JSON with Accept: application/json. The CRUD "
        f"table above uses the JSON admin endpoint {ACCOUNTING_ENDPOINT}.",
    },
    # Master data (extended)
    {
        "area": "Master data",
        "name": "Addressees",
        "path": "/datev/api/master-data/v1/addressees",
    },
    {
        "area": "Master data",
        "name": "Addressee by id",
        "path": "/datev/api/master-data/v1/addressees/{addressee_id}",
        "example_only": True,
        "note": "Path template only — fetch Addressees above and use a real Id.",
    },
    {
        "area": "Master data",
        "name": "Banks",
        "path": "/datev/api/master-data/v1/banks",
    },
    # Accounting (extended, 15 endpoints)
    {"area": "Accounting", "name": "Fiscal years", "path": f"/datev/api/accounting/v1/clients/{_EXAMPLE_CLIENT}/fiscal-years"},
    {"area": "Accounting", "name": "Cost systems", "path": f"{_FY_PREFIX}/cost-systems"},
    {"area": "Accounting", "name": "Cost centers", "path": f"{_FY_PREFIX}/cost-systems/{_EXAMPLE_COST_SYSTEM}/cost-centers"},
    {"area": "Accounting", "name": "Creditors", "path": f"{_FY_PREFIX}/creditors"},
    {"area": "Accounting", "name": "Debitors", "path": f"{_FY_PREFIX}/debitors"},
    {"area": "Accounting", "name": "General ledger accounts", "path": f"{_FY_PREFIX}/general-ledger-accounts"},
    {"area": "Accounting", "name": "Accounts payable", "path": f"{_FY_PREFIX}/accounts-payable"},
    {"area": "Accounting", "name": "Accounts payable (condensed)", "path": f"{_FY_PREFIX}/accounts-payable/condense"},
    {"area": "Accounting", "name": "Accounts receivable (condensed)", "path": f"{_FY_PREFIX}/accounts-receivable/condense"},
    {"area": "Accounting", "name": "Accounting sequences processed", "path": f"{_FY_PREFIX}/accounting-sequences-processed"},
    {"area": "Accounting", "name": "Accounting transaction keys", "path": f"{_FY_PREFIX}/accounting-transaction-keys"},
    {"area": "Accounting", "name": "Asset stocktakings", "path": f"{_FY_PREFIX}/assets/stocktakings"},
    {"area": "Accounting", "name": "Posting proposal rules (incoming invoices)", "path": f"{_FY_PREFIX}/posting-proposal-rules-incoming-invoices"},
    {"area": "Accounting", "name": "Posting proposal rules (outgoing invoices)", "path": f"{_FY_PREFIX}/posting-proposal-rules-outgoing-invoices"},
    {"area": "Accounting", "name": "Terms of payment", "path": f"{_FY_PREFIX}/terms-of-payment"},
    # DMS (extended)
    {"area": "DMS", "name": "Domains", "path": "/datev/api/dms/v1/domains"},
    {"area": "DMS", "name": "Documents", "path": "/datev/api/dms/v1/documents"},
]

assert len(CATALOG) == 23, f"expected 23 catalog entries, got {len(CATALOG)}"


# --- override endpoint key -> real path map (presentational only) ---
#
# Every override-eligible endpoint key (see `app/overrides.py`'s
# `_XML_ROOT_MAP`/`_FINGERPRINTS` and the endpoint-key table in
# `odd/tasks/datev-mock-custom-overrides.md`) mapped to its real, testable
# `/datev/api/...` path, built from the same `_EXAMPLE_CLIENT`/
# `_EXAMPLE_FISCAL_YEAR`/`_EXAMPLE_COST_SYSTEM`/`_FY_PREFIX` constants
# `CATALOG` already uses, for consistency. Used by the admin page to show
# the resolved live URL after a custom-override upload matches an endpoint.

# NOTE (F1, odd/tasks/datev-mock-standalone-frontend.md): this mapping's
# *current values* are duplicated as a hand-baked JS literal in
# frontend/admin.html (the standalone admin page's embedded
# `OVERRIDE_ENDPOINT_PATHS` constant). Editing this mapping does NOT
# automatically update frontend/admin.html — keep them in sync by hand (or
# regenerate frontend/admin.html) until/unless a later epic automates it.
OVERRIDE_ENDPOINT_PATHS: dict[str, str] = {
    "diagnostics.echo": "/datev/api/diagnostics/v1/echo",
    "master_data.clients": "/datev/api/master-data/v1/clients",
    "accounting.clients": "/datev/api/accounting/v1/clients",
    "master_data.addressees": "/datev/api/master-data/v1/addressees",
    "master_data.banks": "/datev/api/master-data/v1/banks",
    "accounting.fiscal_years": f"/datev/api/accounting/v1/clients/{_EXAMPLE_CLIENT}/fiscal-years",
    "accounting.cost_systems": f"{_FY_PREFIX}/cost-systems",
    "accounting.cost_centers": f"{_FY_PREFIX}/cost-systems/{_EXAMPLE_COST_SYSTEM}/cost-centers",
    "accounting.creditors": f"{_FY_PREFIX}/creditors",
    "accounting.debitors": f"{_FY_PREFIX}/debitors",
    "accounting.general_ledger_accounts": f"{_FY_PREFIX}/general-ledger-accounts",
    "accounting.accounts_payable": f"{_FY_PREFIX}/accounts-payable",
    "accounting.accounts_payable_condense": f"{_FY_PREFIX}/accounts-payable/condense",
    "accounting.accounts_receivable_condense": f"{_FY_PREFIX}/accounts-receivable/condense",
    "accounting.accounting_sequences_processed": f"{_FY_PREFIX}/accounting-sequences-processed",
    "accounting.accounting_transaction_keys": f"{_FY_PREFIX}/accounting-transaction-keys",
    "accounting.assets_stocktakings": f"{_FY_PREFIX}/assets/stocktakings",
    "accounting.posting_proposal_rules_incoming": f"{_FY_PREFIX}/posting-proposal-rules-incoming-invoices",
    "accounting.posting_proposal_rules_outgoing": f"{_FY_PREFIX}/posting-proposal-rules-outgoing-invoices",
    "accounting.terms_of_payment": f"{_FY_PREFIX}/terms-of-payment",
    "dms.domains": "/datev/api/dms/v1/domains",
    "dms.documents": "/datev/api/dms/v1/documents",
}

assert len(OVERRIDE_ENDPOINT_PATHS) == 22, (
    f"expected 22 override endpoint keys, got {len(OVERRIDE_ENDPOINT_PATHS)}"
)


# --- HTML page ---
#
# The admin page's HTML/CSS/JS lives in frontend/admin.html (extracted from
# this module's former inline _PAGE string in F1 of
# odd/tasks/datev-mock-standalone-frontend.md) as a genuinely self-contained
# static file — openable via file:// or any static file server, no backend
# needed to render its shell. GET /admin below just serves that file's bytes
# verbatim; its route path, method, and response content-type are unchanged
# from before the extraction.
#
# Read-once-and-cache: the file is read from disk the first time GET /admin
# is served (or FRONTEND_ADMIN_HTML_PATH.read_text() is otherwise called) and
# kept in _ADMIN_PAGE_CACHE for the life of the process, since its content is
# static and does not change at runtime. Restart the process to pick up
# hand edits to frontend/admin.html.

FRONTEND_ADMIN_HTML_PATH = Path(__file__).resolve().parent.parent.parent / "frontend" / "admin.html"

_ADMIN_PAGE_CACHE: str | None = None


def _load_admin_page_html() -> str:
    global _ADMIN_PAGE_CACHE
    if _ADMIN_PAGE_CACHE is None:
        _ADMIN_PAGE_CACHE = FRONTEND_ADMIN_HTML_PATH.read_text(encoding="utf-8")
    return _ADMIN_PAGE_CACHE


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    return HTMLResponse(content=_load_admin_page_html())
