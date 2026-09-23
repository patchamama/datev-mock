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

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import config, data_store

router = APIRouter(tags=["admin"])

SETTINGS_ENDPOINT = "/admin/api/settings"
MASTER_DATA_ENDPOINT = "/admin/api/clients/master-data"
ACCOUNTING_ENDPOINT = "/admin/api/clients/accounting"
RESET_ENDPOINT = "/admin/api/reset"


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


# --- HTML page ---

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DATEV Mock — Admin</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
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
  <div class="card-header">
    Master-data clients
    <div class="small text-muted mt-1">
      Real endpoint: <code>GET /datev/api/master-data/v1/clients</code> (XML). This table
      edits via the JSON admin endpoint <code>/admin/api/clients/master-data</code> instead
      &mdash; two different things.
      <a href="https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data" target="_blank" rel="noopener">DATEV docs</a>
    </div>
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
  </div>
</div>

<div class="card mb-4">
  <div class="card-header">
    Accounting clients
    <div class="small text-muted mt-1">
      Real endpoint: <code>GET /datev/api/accounting/v1/clients</code> (XML by default, JSON
      with <code>Accept: application/json</code>). This table edits via the JSON admin
      endpoint <code>/admin/api/clients/accounting</code> instead &mdash; two different things.
      <a href="https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting" target="_blank" rel="noopener">DATEV docs</a>
    </div>
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
  </div>
</div>

<div class="card mb-4">
  <div class="card-header">Reset</div>
  <div class="card-body">
    <button id="reset-btn" type="button" class="btn btn-outline-danger">Reset all data to defaults</button>
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

</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
const SETTINGS_URL = "/admin/api/settings";
const MASTER_DATA_URL = "/admin/api/clients/master-data";
const ACCOUNTING_URL = "/admin/api/clients/accounting";
const RESET_URL = "/admin/api/reset";
const CATALOG = __CATALOG_JSON__;

// Confirmed DATEV documentation URLs, per catalog area (see
// odd/tasks/datev-mock-admin-ui-polish.md "Follow-on" section). Diagnostics
// and DMS intentionally have no confirmed URL and are omitted here.
const AREA_DOCS = {
  "Master data": "https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data",
  "Accounting": "https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting",
};

const state = { port: 58452 };

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

// --- API catalog ---

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function buildCurl(path) {
  return `curl -k https://127.0.0.1:${state.port}${path}`;
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

async function fetchSample(path, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="text-muted small">Loading&hellip;</div>';
  try {
    const res = await fetch(path);
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      container.innerHTML = renderJsonSample(data);
    } else {
      const text = await res.text();
      container.innerHTML = `<pre class="bg-light border rounded p-2 small mb-0 catalog-sample">${escapeHtml(text)}</pre>`;
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

loadSettings();
loadMasterData();
loadAccounting();
renderCatalog();
</script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    page = _PAGE.replace("__CATALOG_JSON__", json.dumps(CATALOG))
    return HTMLResponse(content=page)
