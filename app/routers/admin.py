"""Admin/settings UI and JSON API (`/admin`, `/admin/api/*`).

`GET /admin` serves a single self-contained HTML page (inline CSS/JS, no
build step, no frontend framework) that drives the JSON API below via
`fetch()`. See `odd/tasks/datev-mock-settings.md` for the locked-in contract.
"""
from __future__ import annotations

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


# --- HTML page ---

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DATEV Mock — Admin</title>
<style>
  body { font-family: sans-serif; margin: 2rem; max-width: 60rem; }
  h1, h2 { margin-top: 2rem; }
  table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
  th, td { border: 1px solid #ccc; padding: 0.35rem 0.6rem; text-align: left; font-size: 0.9rem; }
  th { background: #f0f0f0; }
  form.inline { display: inline; }
  #settings-note { color: #a00; font-weight: bold; }
  fieldset { margin-top: 1rem; }
  button { cursor: pointer; }
</style>
</head>
<body>
<h1>DATEV Mock — Admin</h1>

<section>
  <h2>Settings</h2>
  <label>Port: <input id="settings-port" type="number" min="1" max="65535"></label>
  <label>Default accounting format:
    <select id="settings-format">
      <option value="xml">xml</option>
      <option value="json">json</option>
    </select>
  </label>
  <button id="settings-save">Save</button>
  <div id="settings-note"></div>
</section>

<section>
  <h2>Master-data clients</h2>
  <table id="master-data-table">
    <thead><tr><th>Id</th><th>Name</th><th>Number</th><th>Status</th><th>Type</th><th>Actions</th></tr></thead>
    <tbody></tbody>
  </table>
  <fieldset>
    <legend>Add master-data client</legend>
    <input id="md-name" placeholder="Name">
    <input id="md-number" type="number" placeholder="Number">
    <select id="md-status"><option value="active">active</option><option value="inactive">inactive</option></select>
    <select id="md-type"><option value="legal_person">legal_person</option><option value="natural_person">natural_person</option></select>
    <button id="md-add">Add</button>
  </fieldset>
</section>

<section>
  <h2>Accounting clients</h2>
  <table id="accounting-table">
    <thead><tr><th>Id</th><th>Name</th><th>Number</th><th>Actions</th></tr></thead>
    <tbody></tbody>
  </table>
  <fieldset>
    <legend>Add accounting client</legend>
    <input id="ac-name" placeholder="Name">
    <input id="ac-number" type="number" placeholder="Number">
    <button id="ac-add">Add</button>
  </fieldset>
</section>

<section>
  <h2>Reset</h2>
  <button id="reset-btn">Reset all data to defaults</button>
</section>

<script>
const SETTINGS_URL = "/admin/api/settings";
const MASTER_DATA_URL = "/admin/api/clients/master-data";
const ACCOUNTING_URL = "/admin/api/clients/accounting";
const RESET_URL = "/admin/api/reset";

async function loadSettings() {
  const res = await fetch(SETTINGS_URL);
  const data = await res.json();
  document.getElementById("settings-port").value = data.port;
  document.getElementById("settings-format").value = data.default_accounting_format;
  document.getElementById("settings-note").textContent = "";
}

async function saveSettings() {
  const port = parseInt(document.getElementById("settings-port").value, 10);
  const default_accounting_format = document.getElementById("settings-format").value;
  const res = await fetch(SETTINGS_URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ port, default_accounting_format }),
  });
  const note = document.getElementById("settings-note");
  if (!res.ok) {
    note.textContent = "Failed to save settings — check port/format values.";
    return;
  }
  const data = await res.json();
  note.textContent = data.restart_required
    ? "Restart the server for the new port to take effect."
    : "";
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
      <button data-action="edit">Edit</button>
      <button data-action="delete">Delete</button>
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
      <button data-action="edit">Edit</button>
      <button data-action="delete">Delete</button>
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

loadSettings();
loadMasterData();
loadAccounting();
</script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    return HTMLResponse(content=_PAGE)
