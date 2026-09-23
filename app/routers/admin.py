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
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import config, data_store, overrides, request_log

router = APIRouter(tags=["admin"])

SETTINGS_ENDPOINT = "/admin/api/settings"
MASTER_DATA_ENDPOINT = "/admin/api/clients/master-data"
ACCOUNTING_ENDPOINT = "/admin/api/clients/accounting"
RESET_ENDPOINT = "/admin/api/reset"
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


# --- settings ---


@router.get(SETTINGS_ENDPOINT)
def get_settings() -> dict:
    return asdict(config.load_settings())


@router.put(SETTINGS_ENDPOINT)
def put_settings(payload: SettingsPayload) -> dict:
    previous_port = config.load_settings().port

    try:
        new_settings = config.Settings(
            port=payload.port, default_accounting_format=payload.default_accounting_format
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

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DATEV Mock — Admin</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.2/styles/default.min.css" rel="stylesheet">
<style>
  body { padding-bottom: 3rem; background: #f8f9fa; }
  main { max-width: 64rem; margin: 0 auto; padding: 1.5rem 1rem; }
  code { word-break: break-all; }
  .scroll-table { max-height: 24rem; overflow: auto; }
  .catalog-sample { max-height: 18rem; overflow: auto; }
</style>
</head>
<body>
<nav class="navbar navbar-dark bg-dark mb-4">
  <div class="container-fluid d-flex justify-content-between align-items-center" style="max-width: 64rem; margin: 0 auto;">
    <span class="navbar-brand mb-0 h1">DATEV Mock &mdash; Admin</span>
    <a href="/docs" target="_blank" rel="noopener" class="btn btn-outline-light btn-sm">API Docs (Swagger)</a>
  </div>
</nav>

<main>

<div class="card mb-4">
  <div class="card-header">Settings</div>
  <div class="card-body">
    <form id="settings-form" class="row gy-2 gx-3 align-items-end">
      <div class="col-auto">
        <label for="settings-port" class="form-label">Port</label>
        <input id="settings-port" type="number" min="1" max="65535" class="form-control">
      </div>
      <div class="col-auto">
        <label for="settings-format" class="form-label">Default accounting format</label>
        <select id="settings-format" class="form-select">
          <option value="xml">xml</option>
          <option value="json">json</option>
        </select>
      </div>
      <div class="col-auto">
        <button id="settings-save" type="button" class="btn btn-primary">Save</button>
      </div>
    </form>
    <div id="settings-note" class="alert mt-3 d-none" role="alert"></div>
  </div>
</div>

<div class="card mb-4">
  <div class="card-header d-flex justify-content-between align-items-start gap-2">
    <div>
      Master-data clients
      <div class="small text-muted mt-1">
        Real endpoint: <code>GET /datev/api/master-data/v1/clients</code> (XML). This table
        edits via the JSON admin endpoint <code>/admin/api/clients/master-data</code> instead
        &mdash; two different things.
        <a href="https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data" target="_blank" rel="noopener">DATEV docs</a>
      </div>
    </div>
    <button id="md-export-csv" type="button" class="btn btn-sm btn-outline-secondary text-nowrap">Export CSV</button>
  </div>
  <div class="card-body">
    <div class="table-responsive scroll-table">
      <table class="table table-sm table-striped align-middle" id="master-data-table">
        <thead class="table-light"><tr><th>Id</th><th>Name</th><th>Number</th><th>Status</th><th>Type</th><th>Actions</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <fieldset class="border rounded p-3 mt-2">
      <legend class="float-none w-auto px-2 fs-6">Add master-data client</legend>
      <div class="row g-2 align-items-end">
        <div class="col-auto"><input id="md-name" class="form-control form-control-sm" placeholder="Name"></div>
        <div class="col-auto"><input id="md-number" type="number" class="form-control form-control-sm" placeholder="Number"></div>
        <div class="col-auto">
          <select id="md-status" class="form-select form-select-sm">
            <option value="active">active</option>
            <option value="inactive">inactive</option>
          </select>
        </div>
        <div class="col-auto">
          <select id="md-type" class="form-select form-select-sm">
            <option value="legal_person">legal_person</option>
            <option value="natural_person">natural_person</option>
          </select>
        </div>
        <div class="col-auto"><button id="md-add" type="button" class="btn btn-sm btn-success">Add</button></div>
      </div>
    </fieldset>
    <fieldset class="border rounded p-3 mt-2">
      <legend class="float-none w-auto px-2 fs-6">Import master-data clients (CSV)</legend>
      <div class="row g-2 align-items-end">
        <div class="col-auto"><input id="md-import-file" type="file" accept=".csv" class="form-control form-control-sm"></div>
        <div class="col-auto"><button id="md-import-btn" type="button" class="btn btn-sm btn-primary">Import CSV</button></div>
      </div>
      <div class="small text-muted mt-2">Columns used: <code>Name</code>, <code>Number</code>, <code>Status</code>, <code>Type</code> (other columns are ignored).</div>
      <div id="md-import-result" class="mt-2"></div>
    </fieldset>
  </div>
</div>

<div class="card mb-4">
  <div class="card-header d-flex justify-content-between align-items-start gap-2">
    <div>
      Accounting clients
      <div class="small text-muted mt-1">
        Real endpoint: <code>GET /datev/api/accounting/v1/clients</code> (XML by default, JSON
        with <code>Accept: application/json</code>). This table edits via the JSON admin
        endpoint <code>/admin/api/clients/accounting</code> instead &mdash; two different things.
        <a href="https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting" target="_blank" rel="noopener">DATEV docs</a>
      </div>
    </div>
    <button id="ac-export-csv" type="button" class="btn btn-sm btn-outline-secondary text-nowrap">Export CSV</button>
  </div>
  <div class="card-body">
    <div class="table-responsive scroll-table">
      <table class="table table-sm table-striped align-middle" id="accounting-table">
        <thead class="table-light"><tr><th>Id</th><th>Name</th><th>Number</th><th>Actions</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <fieldset class="border rounded p-3 mt-2">
      <legend class="float-none w-auto px-2 fs-6">Add accounting client</legend>
      <div class="row g-2 align-items-end">
        <div class="col-auto"><input id="ac-name" class="form-control form-control-sm" placeholder="Name"></div>
        <div class="col-auto"><input id="ac-number" type="number" class="form-control form-control-sm" placeholder="Number"></div>
        <div class="col-auto"><button id="ac-add" type="button" class="btn btn-sm btn-success">Add</button></div>
      </div>
    </fieldset>
    <fieldset class="border rounded p-3 mt-2">
      <legend class="float-none w-auto px-2 fs-6">Import accounting clients (CSV)</legend>
      <div class="row g-2 align-items-end">
        <div class="col-auto"><input id="ac-import-file" type="file" accept=".csv" class="form-control form-control-sm"></div>
        <div class="col-auto"><button id="ac-import-btn" type="button" class="btn btn-sm btn-primary">Import CSV</button></div>
      </div>
      <div class="small text-muted mt-2">Columns used: <code>Name</code>, <code>Number</code> (other columns are ignored).</div>
      <div id="ac-import-result" class="mt-2"></div>
    </fieldset>
  </div>
</div>

<div class="card mb-4">
  <div class="card-header">Reset</div>
  <div class="card-body">
    <button id="reset-btn" type="button" class="btn btn-outline-danger">Reset all data to defaults</button>
  </div>
</div>

<div class="card mb-4" id="overrides-card">
  <div class="card-header">Custom Examples (Overrides)</div>
  <div class="card-body">
    <p class="text-muted small">
      Upload an XML or JSON file to temporarily override a mocked endpoint's
      response with your own example data. The endpoint is detected
      automatically from the file's structure &mdash; nothing is persisted to
      disk, and overrides are lost on restart.
    </p>
    <form id="override-upload-form" class="row gy-2 gx-3 align-items-end">
      <div class="col-auto">
        <label for="override-file" class="form-label">XML or JSON file</label>
        <input id="override-file" type="file" accept=".xml,.json" class="form-control form-control-sm">
      </div>
      <div class="col-auto">
        <button id="override-upload-btn" type="button" class="btn btn-sm btn-primary">Upload &amp; Detect</button>
      </div>
      <div class="col-auto">
        <label for="override-folder-input" class="form-label">Folder (XML/JSON files)</label>
        <input id="override-folder-input" type="file" webkitdirectory multiple class="form-control form-control-sm">
      </div>
      <div class="col-auto">
        <button id="override-folder-import-btn" type="button" class="btn btn-sm btn-primary">Import Folder</button>
      </div>
    </form>
    <div id="override-upload-result" class="mt-3"></div>
    <div id="override-folder-import-result" class="mt-3"></div>
    <div class="table-responsive scroll-table mt-3">
      <table class="table table-sm table-striped align-middle" id="overrides-table">
        <thead class="table-light">
          <tr><th>Endpoint</th><th>Filename</th><th>Type</th><th>Uploaded</th><th>Enabled</th><th>Actions</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
    <div id="overrides-empty" class="text-muted small d-none">No custom overrides uploaded yet.</div>
  </div>
</div>

<div class="card mb-4">
  <div class="card-header">API Catalog</div>
  <div class="card-body">
    <p class="text-muted small">
      Every mocked GET endpoint, grouped by area. Sample data is fetched on
      demand (click &ldquo;View sample data&rdquo;) &mdash; nothing here loads
      automatically. Accounting path values (<code>example-client-id</code>,
      <code>example-fiscal-year-id</code>, <code>example-cost-system-id</code>)
      are illustrative only: this mock returns the same data regardless of
      the values supplied.
    </p>
    <div class="accordion" id="catalog-accordion"></div>
  </div>
</div>

<div class="card mb-4" id="request-log-card">
  <div class="card-header d-flex justify-content-between align-items-start gap-2">
    <div>
      Live Request Log
      <div class="small text-muted mt-1">
        Every request this mock receives, live via Server-Sent Events &mdash;
        newest first. A row with a
        <span class="badge text-bg-danger">UNMATCHED</span> badge hit no
        registered route at all (a real gap in this mock's coverage) &mdash;
        different from a route that matched and legitimately returned an
        error on its own (e.g. addressee-by-id for an unknown id). Click a
        row to see the full request/response detail.
      </div>
    </div>
    <span id="request-log-status" class="badge text-bg-secondary text-nowrap">Connecting&hellip;</span>
  </div>
  <div class="card-body">
    <div class="row g-2 align-items-end mb-3">
      <div class="col-auto">
        <label for="request-log-filter" class="form-label">Filter by path</label>
        <input id="request-log-filter" type="text" class="form-control form-control-sm" placeholder="e.g. addressees">
      </div>
      <div class="col-auto">
        <div class="form-check form-switch mt-4">
          <input id="request-log-unmatched-only" class="form-check-input" type="checkbox" role="switch">
          <label class="form-check-label" for="request-log-unmatched-only">Unmatched/errors only</label>
        </div>
      </div>
      <div class="col-auto ms-auto">
        <button id="request-log-clear" type="button" class="btn btn-sm btn-outline-secondary">Clear view</button>
      </div>
    </div>
    <div class="table-responsive scroll-table">
      <table class="table table-sm table-striped align-middle mb-0" id="request-log-table">
        <thead class="table-light"><tr><th>Time</th><th>Method</th><th>Path</th><th>Status</th><th>Duration</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div id="request-log-empty" class="text-muted small mt-2">No requests captured yet.</div>
  </div>
</div>

</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.2/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.2/languages/xml.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.2/languages/json.min.js"></script>
<script>
const SETTINGS_URL = "/admin/api/settings";
const MASTER_DATA_URL = "/admin/api/clients/master-data";
const ACCOUNTING_URL = "/admin/api/clients/accounting";
const RESET_URL = "/admin/api/reset";
const OVERRIDES_URL = "/admin/api/overrides";
const OVERRIDES_RESOLVE_URL = "/admin/api/overrides/resolve";
const CATALOG = __CATALOG_JSON__;
const OVERRIDE_ENDPOINT_PATHS = __OVERRIDE_PATHS_JSON__;

// Confirmed DATEV documentation URLs, per catalog area (see
// odd/tasks/datev-mock-admin-ui-polish.md "Follow-on" section). Diagnostics
// and DMS intentionally have no confirmed URL and are omitted here.
const AREA_DOCS = {
  "Master data": "https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data",
  "Accounting": "https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting",
};

const state = { port: 58452 };
let masterDataRecords = [];
let accountingRecords = [];
let ambiguousQueue = [];

function showNote(message, kind) {
  const note = document.getElementById("settings-note");
  note.classList.remove("d-none", "alert-warning", "alert-danger", "alert-success");
  if (!message) {
    note.classList.add("d-none");
    note.textContent = "";
    return;
  }
  note.classList.add(kind || "alert-warning");
  note.textContent = message;
}

async function loadSettings() {
  const res = await fetch(SETTINGS_URL);
  const data = await res.json();
  document.getElementById("settings-port").value = data.port;
  document.getElementById("settings-format").value = data.default_accounting_format;
  state.port = data.port;
  showNote("");
}

async function saveSettings() {
  const port = parseInt(document.getElementById("settings-port").value, 10);
  const default_accounting_format = document.getElementById("settings-format").value;
  const res = await fetch(SETTINGS_URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port, default_accounting_format }),
  });
  if (!res.ok) {
    showNote("Failed to save settings — check port/format values.", "alert-danger");
    return;
  }
  const data = await res.json();
  state.port = data.port;
  showNote(
    data.restart_required ? "Restart the server for the new port to take effect." : ""
  );
}

function renderMasterDataRow(record) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td>${record.Id}</td>
    <td>${record.Name}</td>
    <td>${record.Number}</td>
    <td>${record.Status}</td>
    <td>${record.Type}</td>
    <td>
      <button class="btn btn-sm btn-outline-secondary" data-action="edit">Edit</button>
      <button class="btn btn-sm btn-outline-danger" data-action="delete">Delete</button>
    </td>`;
  tr.querySelector('[data-action="edit"]').addEventListener("click", async () => {
    const name = prompt("New name?", record.Name);
    if (name === null) return;
    await fetch(`${MASTER_DATA_URL}/${record.Id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ Name: name }),
    });
    loadMasterData();
  });
  tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    await fetch(`${MASTER_DATA_URL}/${record.Id}`, { method: "DELETE" });
    loadMasterData();
  });
  return tr;
}

async function loadMasterData() {
  const res = await fetch(MASTER_DATA_URL);
  const records = await res.json();
  masterDataRecords = records;
  const tbody = document.querySelector("#master-data-table tbody");
  tbody.innerHTML = "";
  records.forEach((record) => tbody.appendChild(renderMasterDataRow(record)));
}

function renderAccountingRow(record) {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td>${record.Id}</td>
    <td>${record.Name}</td>
    <td>${record.Number}</td>
    <td>
      <button class="btn btn-sm btn-outline-secondary" data-action="edit">Edit</button>
      <button class="btn btn-sm btn-outline-danger" data-action="delete">Delete</button>
    </td>`;
  tr.querySelector('[data-action="edit"]').addEventListener("click", async () => {
    const name = prompt("New name?", record.Name);
    if (name === null) return;
    await fetch(`${ACCOUNTING_URL}/${record.Id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ Name: name }),
    });
    loadAccounting();
  });
  tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    await fetch(`${ACCOUNTING_URL}/${record.Id}`, { method: "DELETE" });
    loadAccounting();
  });
  return tr;
}

async function loadAccounting() {
  const res = await fetch(ACCOUNTING_URL);
  const records = await res.json();
  accountingRecords = records;
  const tbody = document.querySelector("#accounting-table tbody");
  tbody.innerHTML = "";
  records.forEach((record) => tbody.appendChild(renderAccountingRow(record)));
}

document.getElementById("settings-save").addEventListener("click", saveSettings);

document.getElementById("md-add").addEventListener("click", async () => {
  const Name = document.getElementById("md-name").value;
  const Number = parseInt(document.getElementById("md-number").value, 10) || 0;
  const Status = document.getElementById("md-status").value;
  const Type = document.getElementById("md-type").value;
  await fetch(MASTER_DATA_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ Name, Number, Status, Type }),
  });
  loadMasterData();
});

document.getElementById("ac-add").addEventListener("click", async () => {
  const Name = document.getElementById("ac-name").value;
  const Number = parseInt(document.getElementById("ac-number").value, 10) || 0;
  await fetch(ACCOUNTING_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ Name, Number }),
  });
  loadAccounting();
});

document.getElementById("reset-btn").addEventListener("click", async () => {
  await fetch(RESET_URL, { method: "POST" });
  loadMasterData();
  loadAccounting();
});

// --- CSV export/import (client-side only; no new backend endpoints) ---

function csvQuoteField(value) {
  const text = value === null || value === undefined ? "" : String(value);
  if (/[",\\r\\n]/.test(text)) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
}

function toCsv(rows) {
  if (!rows.length) return "";
  const columns = [];
  const seen = new Set();
  rows.forEach((row) => {
    Object.keys(row).forEach((key) => {
      if (!seen.has(key)) {
        seen.add(key);
        columns.push(key);
      }
    });
  });
  const lines = [columns.map(csvQuoteField).join(",")];
  rows.forEach((row) => {
    lines.push(columns.map((col) => csvQuoteField(row[col])).join(","));
  });
  return lines.join("\\r\\n");
}

// RFC4180-aware parser: handles quoted fields with embedded commas,
// quotes ("" for an escaped quote) and newlines. First row is the header.
function fromCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      field += ch;
      i += 1;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (ch === ",") {
      row.push(field);
      field = "";
      i += 1;
      continue;
    }
    if (ch === "\\r") {
      i += 1;
      continue;
    }
    if (ch === "\\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      i += 1;
      continue;
    }
    field += ch;
    i += 1;
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) return [];
  const header = rows[0];
  const records = [];
  for (let r = 1; r < rows.length; r += 1) {
    const values = rows[r];
    if (values.length === 1 && values[0] === "") continue; // skip blank/trailing line
    const record = {};
    header.forEach((col, idx) => {
      record[col] = values[idx] !== undefined ? values[idx] : "";
    });
    records.push(record);
  }
  return records;
}

// Every top-level key that holds an object (e.g. accounting's `company_data`)
// on ANY record gets flattened to `parent.child` columns; a record where
// that same key is null simply leaves those columns empty for its row.
function collectObjectKeys(records) {
  const objectKeys = new Set();
  records.forEach((record) => {
    Object.keys(record).forEach((key) => {
      const value = record[key];
      if (value !== null && typeof value === "object" && !Array.isArray(value)) {
        objectKeys.add(key);
      }
    });
  });
  return objectKeys;
}

function flattenRecord(record, objectKeys) {
  const flat = {};
  Object.keys(record).forEach((key) => {
    const value = record[key];
    if (objectKeys.has(key)) {
      if (value !== null && typeof value === "object") {
        Object.keys(value).forEach((childKey) => {
          flat[`${key}.${childKey}`] = value[childKey];
        });
      }
      return;
    }
    flat[key] = value;
  });
  return flat;
}

function recordsToCsv(records) {
  const objectKeys = collectObjectKeys(records);
  const flatRows = records.map((record) => flattenRecord(record, objectKeys));
  return toCsv(flatRows);
}

function downloadCsv(filename, csvText) {
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function importCsvRows(file, postUrl, buildFields) {
  const text = await file.text();
  const rows = fromCsv(text);
  let imported = 0;
  let failed = 0;
  for (const row of rows) {
    const fields = buildFields(row);
    try {
      const res = await fetch(postUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (res.ok) {
        imported += 1;
      } else {
        failed += 1;
      }
    } catch (err) {
      failed += 1;
    }
  }
  return { imported, failed, total: rows.length };
}

function showImportResult(elementId, outcome) {
  const el = document.getElementById(elementId);
  const kind = outcome.failed > 0 ? "alert-warning" : "alert-success";
  const failedNote = outcome.failed > 0 ? ` (${outcome.failed} failed)` : "";
  el.innerHTML = `<div class="alert ${kind}">Imported ${outcome.imported} of ${outcome.total} rows${failedNote}.</div>`;
}

document.getElementById("md-export-csv").addEventListener("click", () => {
  downloadCsv("master-data-clients.csv", recordsToCsv(masterDataRecords));
});

document.getElementById("ac-export-csv").addEventListener("click", () => {
  downloadCsv("accounting-clients.csv", recordsToCsv(accountingRecords));
});

document.getElementById("md-import-btn").addEventListener("click", async () => {
  const input = document.getElementById("md-import-file");
  const file = input.files && input.files[0];
  if (!file) {
    document.getElementById("md-import-result").innerHTML =
      '<div class="alert alert-warning">Choose a CSV file first.</div>';
    return;
  }
  const outcome = await importCsvRows(file, MASTER_DATA_URL, (row) => {
    const fields = {};
    if ("Name" in row) fields.Name = row.Name;
    if ("Number" in row) fields.Number = parseInt(row.Number, 10) || 0;
    if ("Status" in row) fields.Status = row.Status;
    if ("Type" in row) fields.Type = row.Type;
    return fields;
  });
  input.value = "";
  showImportResult("md-import-result", outcome);
  loadMasterData();
});

document.getElementById("ac-import-btn").addEventListener("click", async () => {
  const input = document.getElementById("ac-import-file");
  const file = input.files && input.files[0];
  if (!file) {
    document.getElementById("ac-import-result").innerHTML =
      '<div class="alert alert-warning">Choose a CSV file first.</div>';
    return;
  }
  const outcome = await importCsvRows(file, ACCOUNTING_URL, (row) => {
    const fields = {};
    if ("Name" in row) fields.Name = row.Name;
    if ("Number" in row) fields.Number = parseInt(row.Number, 10) || 0;
    return fields;
  });
  input.value = "";
  showImportResult("ac-import-result", outcome);
  loadAccounting();
});

// --- custom overrides ---

function overrideEscapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function showOverrideUploadResult(html) {
  document.getElementById("override-upload-result").innerHTML = html;
}

function overrideMatchedResultHtml(key) {
  const path = OVERRIDE_ENDPOINT_PATHS[key];
  let endpointHtml = "";
  if (path) {
    const url = buildUrl(path);
    endpointHtml = `<div class="mt-1">Endpoint: <code>GET ${overrideEscapeHtml(url)}</code> &mdash; <a href="${overrideEscapeHtml(url)}" target="_blank" rel="noopener">open</a></div>`;
  }
  return `<div class="alert alert-success">Matched to endpoint: <code>${overrideEscapeHtml(key)}</code>. Override is now active.${endpointHtml}</div>`;
}

function renderOverrideRow(key, meta) {
  const tr = document.createElement("tr");
  const badgeClass = meta.content_type === "xml" ? "text-bg-info" : "text-bg-secondary";
  tr.innerHTML = `
    <td><code>${overrideEscapeHtml(key)}</code></td>
    <td>${overrideEscapeHtml(meta.filename)}</td>
    <td><span class="badge ${badgeClass}">${overrideEscapeHtml(meta.content_type)}</span></td>
    <td class="small text-muted">${overrideEscapeHtml(meta.uploaded_at)}</td>
    <td>
      <div class="form-check form-switch mb-0">
        <input class="form-check-input" type="checkbox" role="switch" data-action="toggle" ${meta.enabled ? "checked" : ""}>
      </div>
    </td>
    <td>
      <button class="btn btn-sm btn-outline-danger" data-action="delete">Delete</button>
    </td>`;
  tr.querySelector('[data-action="toggle"]').addEventListener("change", async (ev) => {
    await fetch(`${OVERRIDES_URL}/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: ev.target.checked }),
    });
    loadOverrides();
  });
  tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    await fetch(`${OVERRIDES_URL}/${encodeURIComponent(key)}`, { method: "DELETE" });
    loadOverrides();
  });
  return tr;
}

async function loadOverrides() {
  const res = await fetch(OVERRIDES_URL);
  const data = await res.json();
  const tbody = document.querySelector("#overrides-table tbody");
  const empty = document.getElementById("overrides-empty");
  tbody.innerHTML = "";
  const keys = Object.keys(data);
  keys.forEach((key) => tbody.appendChild(renderOverrideRow(key, data[key])));
  empty.classList.toggle("d-none", keys.length > 0);
}

// `onResolved` runs after a successful individual resolution, defaulting to
// a plain `loadOverrides()` refresh (the single-upload flow). The folder
// import flow below passes its own callback that also advances to the next
// queued ambiguous file, reusing this exact same resolution UI rather than
// building a second one.
function renderAmbiguousChoiceForm(candidates, pendingId, filename, onResolved) {
  const resolve = onResolved || loadOverrides;
  const options = candidates
    .map(
      (candidate, idx) => `
      <div class="form-check">
        <input class="form-check-input" type="radio" name="override-candidate" id="override-candidate-${idx}" value="${overrideEscapeHtml(candidate)}" ${idx === 0 ? "checked" : ""}>
        <label class="form-check-label" for="override-candidate-${idx}"><code>${overrideEscapeHtml(candidate)}</code></label>
      </div>`
    )
    .join("");
  const filenameNote = filename
    ? `<p class="mb-1 small text-muted">File: <code>${overrideEscapeHtml(filename)}</code></p>`
    : "";
  showOverrideUploadResult(`
    <div class="alert alert-warning">
      ${filenameNote}
      <p class="mb-2">This data matches multiple endpoints with an identical shape &mdash; pick which one you mean:</p>
      <form id="override-resolve-form">
        ${options}
        <button type="button" id="override-resolve-btn" class="btn btn-sm btn-primary mt-2">Confirm</button>
      </form>
    </div>`);
  document.getElementById("override-resolve-btn").addEventListener("click", async () => {
    const selected = document.querySelector('input[name="override-candidate"]:checked');
    if (!selected) return;
    const res = await fetch(OVERRIDES_RESOLVE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pending_id: pendingId, endpoint: selected.value }),
    });
    if (!res.ok) {
      showOverrideUploadResult(
        '<div class="alert alert-danger">Failed to resolve override selection.</div>'
      );
      return;
    }
    showOverrideUploadResult(overrideMatchedResultHtml(selected.value));
    resolve();
  });
}

// Shared by both the single-file "Upload & Detect" button and the "Import
// Folder" loop below, so both call exactly the same POST-and-handle logic.
async function postOverrideFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(OVERRIDES_URL, { method: "POST", body: formData });
  return res.json();
}

async function uploadOverrideFile() {
  const input = document.getElementById("override-file");
  const file = input.files && input.files[0];
  if (!file) {
    showOverrideUploadResult('<div class="alert alert-warning">Choose a file first.</div>');
    return;
  }
  const body = await postOverrideFile(file);

  if (body.status === "matched") {
    showOverrideUploadResult(overrideMatchedResultHtml(body.endpoint));
    input.value = "";
    loadOverrides();
    return;
  }

  if (body.status === "ambiguous") {
    renderAmbiguousChoiceForm(body.candidates, body.pending_id);
    input.value = "";
    return;
  }

  showOverrideUploadResult(
    '<div class="alert alert-danger">Could not detect a matching endpoint for this file &mdash; check it matches a response shape this mock recognizes.</div>'
  );
}

document.getElementById("override-upload-btn").addEventListener("click", uploadOverrideFile);

// --- bulk folder import ---

function isXmlOrJsonFilename(name) {
  const lower = name.toLowerCase();
  return lower.endsWith(".xml") || lower.endsWith(".json");
}

// Pops the next queued ambiguous file (populated by importOverrideFolder)
// and shows it in the same resolution UI a single ambiguous upload uses,
// one at a time; resolving it advances to the following queued file, if any.
function showNextAmbiguousFromQueue() {
  if (!ambiguousQueue.length) return;
  const next = ambiguousQueue.shift();
  renderAmbiguousChoiceForm(next.candidates, next.pending_id, next.filename, () => {
    loadOverrides();
    showNextAmbiguousFromQueue();
  });
}

async function importOverrideFolder() {
  const input = document.getElementById("override-folder-input");
  const allFiles = input.files ? Array.from(input.files) : [];
  const resultEl = document.getElementById("override-folder-import-result");
  const files = allFiles.filter((file) => isXmlOrJsonFilename(file.name));

  if (!files.length) {
    resultEl.innerHTML =
      '<div class="alert alert-warning">Choose a folder containing .xml or .json files first.</div>';
    return;
  }

  const matched = [];
  const ambiguous = [];
  const unrecognized = [];

  // Sequential, not parallel: mirrors how CSV import already processes rows
  // one at a time, and avoids overwhelming the backend for a large folder.
  for (const file of files) {
    let body;
    try {
      body = await postOverrideFile(file);
    } catch (err) {
      unrecognized.push(file.name);
      continue;
    }
    if (body.status === "matched") {
      matched.push({ filename: file.name, endpoint: body.endpoint });
    } else if (body.status === "ambiguous") {
      ambiguous.push({ filename: file.name, candidates: body.candidates, pending_id: body.pending_id });
    } else {
      unrecognized.push(file.name);
    }
  }

  const parts = [];
  if (matched.length) {
    const matchedEndpoints = Array.from(new Set(matched.map((m) => m.endpoint)));
    parts.push(`${matched.length} matched (${matchedEndpoints.map(overrideEscapeHtml).join(", ")})`);
  } else {
    parts.push("0 matched");
  }
  if (ambiguous.length) {
    parts.push(`${ambiguous.length} needs manual resolution`);
  }
  if (unrecognized.length) {
    parts.push(`${unrecognized.length} unrecognized (${unrecognized.map(overrideEscapeHtml).join(", ")})`);
  }
  const skipped = allFiles.length - files.length;
  const skippedNote = skipped > 0 ? ` (${skipped} other file${skipped === 1 ? "" : "s"} skipped)` : "";
  const kind = unrecognized.length || ambiguous.length ? "alert-warning" : "alert-success";
  const plural = files.length === 1 ? "" : "s";
  resultEl.innerHTML = `<div class="alert ${kind}">Imported ${files.length} file${plural}: ${parts.join(", ")}.${skippedNote}</div>`;

  input.value = "";
  loadOverrides();

  ambiguousQueue = ambiguous.map((item) => ({
    candidates: item.candidates,
    pending_id: item.pending_id,
    filename: item.filename,
  }));
  showNextAmbiguousFromQueue();
}

document.getElementById("override-folder-import-btn").addEventListener("click", importOverrideFolder);

// --- API catalog ---

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function buildUrl(path) {
  return `https://127.0.0.1:${state.port}${path}`;
}

function buildCurl(path) {
  return `curl -k ${buildUrl(path)}`;
}

async function copyCurl(path, button) {
  const text = buildCurl(path);
  const original = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied!";
  } catch (err) {
    button.textContent = "Copy failed";
  }
  setTimeout(() => { button.textContent = original; }, 1500);
}

function renderJsonSample(data) {
  const records = Array.isArray(data) ? data : [data];
  if (records.length === 0) {
    return '<div class="text-muted small">Empty response.</div>';
  }
  const keys = Object.keys(records[0]);
  const shown = records.slice(0, 20);
  let html = '<div class="table-responsive catalog-sample"><table class="table table-sm table-striped mb-0"><thead><tr>'
    + keys.map((k) => `<th>${escapeHtml(k)}</th>`).join("")
    + "</tr></thead><tbody>";
  shown.forEach((record) => {
    html += "<tr>" + keys.map((k) => `<td>${escapeHtml(String(record[k] ?? ""))}</td>`).join("") + "</tr>";
  });
  html += "</tbody></table></div>";
  if (records.length > shown.length) {
    html += `<div class="text-muted small mt-1">Showing ${shown.length} of ${records.length} records.</div>`;
  }
  return html;
}

// Strips any namespace prefix off an XML tag/attribute name (e.g.
// "i:nil" -> "nil", "ns0:ClientResource" -> "ClientResource") -- conceptually
// the same namespace-stripping app/overrides.py's Python-side detection
// already does, kept here purely for building the Table tab's display data.
function xmlStripNamespace(name) {
  const idx = name.indexOf(":");
  return idx === -1 ? name : name.slice(idx + 1);
}

// DATEV XML marks an absent field as `i:nil="true"` (the XMLSchema-instance
// nil convention) -- checked here regardless of the exact namespace prefix
// bound to that attribute, since it is always that same convention.
function xmlElementIsNil(el) {
  for (let i = 0; i < el.attributes.length; i += 1) {
    const attr = el.attributes[i];
    if (xmlStripNamespace(attr.name) === "nil" && attr.value === "true") {
      return true;
    }
  }
  return false;
}

function xmlElementToObject(el) {
  const obj = {};
  Array.from(el.children).forEach((child) => {
    const key = xmlStripNamespace(child.tagName);
    obj[key] = xmlElementIsNil(child) ? null : child.textContent;
  });
  return obj;
}

// Converts a parsed XML document into an array-of-objects, JSON-like shape
// so the Table tab can reuse the exact same renderJsonSample() builder JSON
// responses already use, instead of a separate XML table renderer.
//   - Repeated root children sharing one tag (e.g. ArrayOfClientResource >
//     ClientResource, ArrayOfClient > Client) each become one row.
//   - Otherwise (e.g. the single-object Echo diagnostic) the root element
//     itself becomes one row, same as renderJsonSample's own single-object
//     fallback already does for a JSON object.
function xmlToRecords(xmlDoc) {
  const root = xmlDoc.documentElement;
  const children = Array.from(root.children);
  if (children.length > 1) {
    const firstTag = xmlStripNamespace(children[0].tagName);
    const allSameTag = children.every((child) => xmlStripNamespace(child.tagName) === firstTag);
    if (allSameTag) {
      return children.map(xmlElementToObject);
    }
  }
  return [xmlElementToObject(root)];
}

// Returns array-of-objects records for the Table tab, or null when `text`
// does not parse as XML at all (DOMParser never throws -- a failed parse
// surfaces as a <parsererror> element instead).
function parseXmlForTable(text) {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  const parserError = doc.getElementsByTagName("parsererror")[0];
  if (parserError || !doc.documentElement) return null;
  return xmlToRecords(doc);
}

async function fetchSample(path, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="text-muted small">Loading&hellip;</div>';
  try {
    const res = await fetch(path);
    const contentType = res.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    const text = await res.text();

    let tableHtml;
    if (isJson) {
      try {
        tableHtml = renderJsonSample(JSON.parse(text));
      } catch (err) {
        tableHtml = '<div class="text-muted small">Could not parse JSON response &mdash; see the Raw tab.</div>';
      }
    } else {
      const records = parseXmlForTable(text);
      if (records) {
        tableHtml = renderJsonSample(records);
      } else {
        tableHtml = '<div class="text-muted small">No tabular view for this content type &mdash; see the Raw tab.</div>';
      }
    }
    const rawLang = isJson ? "json" : "xml";

    // Same idx-based id scheme buildCatalogEntry uses for containerId
    // (catalog-sample-<areaIdx>-<entryIdx>), extended with per-tab suffixes
    // so multiple catalog entries never collide.
    const tableTabId = `${containerId}-tab-table`;
    const rawTabId = `${containerId}-tab-raw`;
    const tablePaneId = `${containerId}-pane-table`;
    const rawPaneId = `${containerId}-pane-raw`;
    const codeId = `${containerId}-code`;
    const tableActive = isJson;

    container.innerHTML = `
      <ul class="nav nav-tabs" role="tablist">
        <li class="nav-item" role="presentation">
          <button class="nav-link ${tableActive ? "active" : ""}" id="${tableTabId}" data-bs-toggle="tab" data-bs-target="#${tablePaneId}" type="button" role="tab" aria-controls="${tablePaneId}" aria-selected="${tableActive}">Table</button>
        </li>
        <li class="nav-item" role="presentation">
          <button class="nav-link ${tableActive ? "" : "active"}" id="${rawTabId}" data-bs-toggle="tab" data-bs-target="#${rawPaneId}" type="button" role="tab" aria-controls="${rawPaneId}" aria-selected="${!tableActive}">Raw</button>
        </li>
      </ul>
      <div class="tab-content border border-top-0 rounded-bottom p-2">
        <div class="tab-pane fade ${tableActive ? "show active" : ""}" id="${tablePaneId}" role="tabpanel" aria-labelledby="${tableTabId}">${tableHtml}</div>
        <div class="tab-pane fade ${tableActive ? "" : "show active"}" id="${rawPaneId}" role="tabpanel" aria-labelledby="${rawTabId}"><pre class="bg-light border-0 rounded p-2 small mb-0 catalog-sample"><code id="${codeId}" class="language-${rawLang}">${escapeHtml(text)}</code></pre></div>
      </div>`;

    const codeEl = document.getElementById(codeId);
    if (codeEl && window.hljs) {
      hljs.highlightElement(codeEl);
    }
  } catch (err) {
    container.innerHTML = `<div class="text-danger small">Failed to fetch: ${escapeHtml(String(err))}</div>`;
  }
}

function buildCatalogEntry(entry, idx) {
  const sampleId = `catalog-sample-${idx}`;
  const action = entry.example_only
    ? '<span class="badge text-bg-secondary align-self-center">Example only</span>'
    : `<button type="button" class="btn btn-sm btn-outline-primary" onclick="fetchSample('${entry.path}', '${sampleId}')">View sample data</button>`;
  const note = entry.note ? `<div class="text-muted small mt-1">${escapeHtml(entry.note)}</div>` : "";
  return `
    <div class="border rounded p-3 mb-2">
      <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
        <div>
          <span class="badge text-bg-success me-2">GET</span>
          <strong>${escapeHtml(entry.name)}</strong>
          <div><code>${escapeHtml(entry.path)}</code></div>
          ${note}
        </div>
        <div class="d-flex gap-2">
          ${action}
          <button type="button" class="btn btn-sm btn-outline-secondary" onclick="copyCurl('${entry.path}', this)">Copy curl</button>
        </div>
      </div>
      <div class="mt-2" id="${sampleId}"></div>
    </div>`;
}

function renderCatalog() {
  const areas = [];
  const byArea = {};
  CATALOG.forEach((entry) => {
    if (!byArea[entry.area]) {
      byArea[entry.area] = [];
      areas.push(entry.area);
    }
    byArea[entry.area].push(entry);
  });

  const accordion = document.getElementById("catalog-accordion");
  accordion.innerHTML = areas
    .map((area, areaIdx) => {
      const collapseId = `catalog-collapse-${areaIdx}`;
      const headingId = `catalog-heading-${areaIdx}`;
      const entriesHtml = byArea[area]
        .map((entry) => buildCatalogEntry(entry, `${areaIdx}-${byArea[area].indexOf(entry)}`))
        .join("");
      const docNote = AREA_DOCS[area]
        ? `<p class="small mb-2"><a href="${AREA_DOCS[area]}" target="_blank" rel="noopener">Official DATEV documentation for ${escapeHtml(area)} &#x2197;</a></p>`
        : "";
      return `
        <div class="accordion-item">
          <h2 class="accordion-header" id="${headingId}">
            <button class="accordion-button ${areaIdx === 0 ? "" : "collapsed"}" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="${areaIdx === 0 ? "true" : "false"}" aria-controls="${collapseId}">
              ${escapeHtml(area)} <span class="badge text-bg-light ms-2">${byArea[area].length}</span>
            </button>
          </h2>
          <div id="${collapseId}" class="accordion-collapse collapse ${areaIdx === 0 ? "show" : ""}" aria-labelledby="${headingId}" data-bs-parent="#catalog-accordion">
            <div class="accordion-body">${docNote}${entriesHtml}</div>
          </div>
        </div>`;
    })
    .join("");
}

// --- live request log ---

const LOGS_STREAM_URL = "/admin/api/logs/stream";
const REQUEST_LOG_MAX_ROWS = 1000;

// Newest-first, kept in sync with what's actually rendered so the path/
// unmatched-only filters can be re-applied client-side without another
// network round trip.
let requestLogEntries = [];

function methodBadgeClass(method) {
  switch (method) {
    case "GET": return "text-bg-primary";
    case "POST": return "text-bg-success";
    case "PUT": return "text-bg-warning";
    case "PATCH": return "text-bg-info";
    case "DELETE": return "text-bg-danger";
    default: return "text-bg-secondary";
  }
}

function statusBadgeClass(status) {
  if (status >= 500) return "text-bg-danger";
  if (status >= 400) return "text-bg-warning";
  if (status >= 300) return "text-bg-info";
  if (status >= 200) return "text-bg-success";
  return "text-bg-secondary";
}

function formatLogTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch (err) {
    return iso;
  }
}

// Picks a highlight.js language for a body preview from its Content-Type --
// this mock's bodies are always JSON or XML (never both at once), same two
// languages the API Catalog's "Raw" tab already loads.
function hljsLangForContentType(contentType) {
  return contentType && contentType.includes("xml") ? "language-xml" : "language-json";
}

function requestLogMatchesFilter(entry) {
  const pathFilter = document.getElementById("request-log-filter").value.trim().toLowerCase();
  const unmatchedOnly = document.getElementById("request-log-unmatched-only").checked;
  if (unmatchedOnly && !entry.unmatched) return false;
  if (pathFilter && !entry.path.toLowerCase().includes(pathFilter)) return false;
  return true;
}

function buildLogDetailHtml(entry) {
  const reqContentType = entry.request_headers && entry.request_headers["content-type"];
  const reqBody = entry.request_body_preview || "(empty)";
  const resBody = entry.response_body_preview || "(empty)";
  return `
    <div class="row g-3">
      <div class="col-md-6">
        <div class="fw-semibold">Request</div>
        <div>Matched route: <code>${escapeHtml(entry.route_path || "(none -- unmatched)")}</code></div>
        <div>Query string: <code>${escapeHtml(entry.query_string || "(none)")}</code></div>
        <div>Path params: <code>${escapeHtml(JSON.stringify(entry.path_params || {}))}</code></div>
        <div>Headers: <code>${escapeHtml(JSON.stringify(entry.request_headers || {}))}</code></div>
        <div class="mt-2 mb-1">Body preview:</div>
        <pre class="bg-light border rounded p-2 mb-0 catalog-sample"><code class="${hljsLangForContentType(reqContentType)}">${escapeHtml(reqBody)}</code></pre>
      </div>
      <div class="col-md-6">
        <div class="fw-semibold">Response</div>
        <div>Status: <code>${entry.response_status}</code></div>
        <div>Content-Type: <code>${escapeHtml(entry.response_content_type || "(none)")}</code></div>
        <div>Duration: <code>${entry.duration_ms.toFixed(1)} ms</code></div>
        <div class="mt-2 mb-1">Body preview:</div>
        <pre class="bg-light border rounded p-2 mb-0 catalog-sample"><code class="${hljsLangForContentType(entry.response_content_type)}">${escapeHtml(resBody)}</code></pre>
      </div>
    </div>`;
}

// Returns [row, detailRow] -- a visible summary row and a collapsed detail
// row toggled by clicking the summary, same "click to expand" idea the API
// Catalog's Raw/Table tabs already use, just without Bootstrap's collapse
// component (a plain class toggle is simpler for a two-row pair like this).
function renderLogRow(entry) {
  const tr = document.createElement("tr");
  tr.style.cursor = "pointer";
  if (entry.unmatched) {
    tr.classList.add("table-danger");
  }
  const unmatchedBadge = entry.unmatched
    ? ' <span class="badge text-bg-danger">UNMATCHED</span>'
    : "";
  tr.innerHTML = `
    <td class="text-nowrap small">${escapeHtml(formatLogTime(entry.timestamp))}</td>
    <td><span class="badge ${methodBadgeClass(entry.method)}">${escapeHtml(entry.method)}</span></td>
    <td><code>${escapeHtml(entry.path)}</code>${unmatchedBadge}</td>
    <td><span class="badge ${statusBadgeClass(entry.response_status)}">${entry.response_status}</span></td>
    <td class="text-nowrap small">${entry.duration_ms.toFixed(1)} ms</td>`;

  const detailRow = document.createElement("tr");
  detailRow.className = "d-none";
  const detailCell = document.createElement("td");
  detailCell.colSpan = 5;
  detailCell.className = "small";
  detailCell.innerHTML = buildLogDetailHtml(entry);
  detailRow.appendChild(detailCell);

  tr.addEventListener("click", () => {
    const wasHidden = detailRow.classList.contains("d-none");
    detailRow.classList.toggle("d-none");
    if (wasHidden && window.hljs) {
      detailCell.querySelectorAll("code").forEach((el) => hljs.highlightElement(el));
    }
  });

  return [tr, detailRow];
}

function renderRequestLogTable() {
  const tbody = document.querySelector("#request-log-table tbody");
  tbody.innerHTML = "";
  const visible = requestLogEntries.filter(requestLogMatchesFilter);
  visible.forEach((entry) => {
    const [tr, detailRow] = renderLogRow(entry);
    tbody.appendChild(tr);
    tbody.appendChild(detailRow);
  });
  document.getElementById("request-log-empty").classList.toggle("d-none", visible.length > 0);
}

// Incremental path for live SSE pushes: prepend just the new row instead of
// re-rendering the whole table, so a long test session doesn't cause
// constant flicker/DOM churn. `renderRequestLogTable()` (full rebuild) is
// used instead whenever the filter itself changes.
function prependLogEntry(entry) {
  requestLogEntries.unshift(entry);
  if (requestLogEntries.length > REQUEST_LOG_MAX_ROWS) {
    requestLogEntries.length = REQUEST_LOG_MAX_ROWS;
  }
  if (!requestLogMatchesFilter(entry)) return;
  const tbody = document.querySelector("#request-log-table tbody");
  const [tr, detailRow] = renderLogRow(entry);
  const firstChild = tbody.firstChild;
  tbody.insertBefore(detailRow, firstChild);
  tbody.insertBefore(tr, detailRow);
  while (tbody.children.length > REQUEST_LOG_MAX_ROWS * 2) {
    tbody.removeChild(tbody.lastChild);
  }
  document.getElementById("request-log-empty").classList.add("d-none");
}

function setRequestLogStatus(text, badgeClass) {
  const el = document.getElementById("request-log-status");
  el.textContent = text;
  el.className = `badge text-nowrap ${badgeClass}`;
}

// SSE (not polling): the backlog arrives as the stream's first batch of
// messages, then live entries as they're broadcast -- one connection gives
// this card everything it needs, so there is no separate initial fetch of
// GET /admin/api/logs here (that endpoint exists for the fallback/
// testability case the task calls for, not for this page).
function connectRequestLogStream() {
  const source = new EventSource(LOGS_STREAM_URL);
  source.onopen = () => setRequestLogStatus("Live", "text-bg-success");
  source.onerror = () => setRequestLogStatus("Disconnected — retrying…", "text-bg-danger");
  source.onmessage = (event) => {
    let entry;
    try {
      entry = JSON.parse(event.data);
    } catch (err) {
      return; // keep-alive comments never reach onmessage; be defensive anyway
    }
    if (requestLogEntries.some((existing) => existing.seq === entry.seq)) return;
    prependLogEntry(entry);
  };
}

document.getElementById("request-log-filter").addEventListener("input", renderRequestLogTable);
document.getElementById("request-log-unmatched-only").addEventListener("change", renderRequestLogTable);
document.getElementById("request-log-clear").addEventListener("click", () => {
  requestLogEntries = [];
  renderRequestLogTable();
});

loadSettings();
loadMasterData();
loadAccounting();
loadOverrides();
renderCatalog();
connectRequestLogStream();
</script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    page = _PAGE.replace("__CATALOG_JSON__", json.dumps(CATALOG))
    page = page.replace("__OVERRIDE_PATHS_JSON__", json.dumps(OVERRIDE_ENDPOINT_PATHS))
    return HTMLResponse(content=page)
