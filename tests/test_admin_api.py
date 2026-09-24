"""RED-phase tests for the `/admin` HTML page and `/admin/api/*` JSON
endpoints (`app/routers/admin.py`, mounted in `app/main.py`).

`app/config.py` does not exist yet (imported below), and neither does
`app/routers/admin.py` nor its mount point in `app/main.py`; this file is
expected to fail on collection with `ModuleNotFoundError` until S1/S2/S3
(GREEN phase) implement them. See `odd/tasks/datev-mock-settings.md` for the
planned contract this test file is designing.

## Test isolation

Unlike the other test modules, these tests mutate shared, process-lifetime
state (the live settings and the in-memory data store), so a **local**,
module-scoped autouse fixture resets both before/after every test:
  - `app.config.SETTINGS_PATH` is monkeypatched to a fresh `tmp_path` file
    per test, so `PUT /admin/api/settings` never touches the real project's
    settings file, and each test starts from the documented defaults
    (port 58452, format "xml") because the fresh tmp file never exists yet.
  - `POST /admin/api/reset` is called to restore both fake-data lists to
    their original generated cardinality before (and after) every test.

This deliberately does **not** touch `tests/conftest.py`. An eager
module-level `import app.config` / `import app.data_store` there would
break collection for *every* other test file (`test_accounting.py`,
`test_master_data.py`, `test_diagnostics.py`, `test_accounting_json.py`)
during this RED phase, not just this one — conftest.py is imported before
any test module in the session. Keeping the isolation fixture local to this
file keeps the blast radius of the still-missing modules contained to this
file's own (expected) collection failure, exactly as instructed: "Do NOT
modify tests/test_accounting.py, tests/test_accounting_json.py,
tests/test_diagnostics.py, or tests/test_master_data.py."

## Contract under test (settled here, for the GREEN implementer)

  - `GET /admin` — 200, `text/html` page (markup itself not asserted).
  - `GET /admin/api/settings` — 200, JSON `{"port": int,
    "default_accounting_format": str}`.
  - `PUT /admin/api/settings` — body requires BOTH fields (full replace, not
    a partial patch): `{"port": int, "default_accounting_format": str}`.
    Response is 200 with the new settings plus a `"restart_required": bool`
    field, true iff the submitted `port` differs from the port that was
    live *before* this call. `default_accounting_format` changes always
    take effect immediately (`restart_required` reflects the port only).
    An invalid `port` (outside 1-65535) or `default_accounting_format`
    (anything other than "xml"/"json") is rejected with a 4xx status and
    leaves settings unchanged.
  - `GET/POST/PUT/DELETE /admin/api/clients/master-data[/{id}]` and
    `GET/POST/PUT/DELETE /admin/api/clients/accounting[/{id}]` — JSON CRUD
    over `app.data_store`. POST returns 200 or 201 with the created record
    (including a fresh, server-generated `"Id"`). PUT on an unknown id
    returns 404. DELETE removes the record (unknown-id DELETE behavior is
    intentionally left unasserted here — `app.data_store.delete_*` is a
    clean no-op per `tests/test_data_store.py`, so the router is free to
    mirror that as a 200 no-op rather than inventing a 404 this task never
    required).
  - `POST /admin/api/reset` — 200, restores both datasets to their original
    generated cardinality (18 master-data / 8 accounting).
"""
from __future__ import annotations

import pytest

from app import config  # noqa: F401  -- RED: app/config.py does not exist yet

ADMIN_PAGE = "/admin"
SETTINGS_ENDPOINT = "/admin/api/settings"
MASTER_DATA_ENDPOINT = "/admin/api/clients/master-data"
ACCOUNTING_ENDPOINT = "/admin/api/clients/accounting"
RESET_ENDPOINT = "/admin/api/reset"
STORED_RECORDS_ENDPOINT = "/admin/api/stored-records"
ACCOUNTING_CLIENTS_ENDPOINT = "/datev/api/accounting/v1/clients"

DEFAULT_PORT = 58452
DEFAULT_FORMAT = "xml"
MASTER_DATA_COUNT = 18
ACCOUNTING_COUNT = 100


@pytest.fixture(autouse=True)
def _isolated_admin_state(tmp_path, monkeypatch, client):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    client.post(RESET_ENDPOINT)
    yield
    client.post(RESET_ENDPOINT)


# --- GET /admin ---


def test_admin_page_returns_200_html(client):
    response = client.get(ADMIN_PAGE)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_admin_page_references_bootstrap_cdn(client):
    # Smoke test for the U1 Bootstrap redesign (see
    # odd/tasks/datev-mock-admin-ui-polish.md) — not asserting exact markup,
    # just that the page actually pulls in Bootstrap from the CDN.
    body = client.get(ADMIN_PAGE).text
    assert "cdn.jsdelivr.net/npm/bootstrap@" in body


def test_admin_page_contains_full_endpoint_catalog_sample(client):
    # Smoke test for the U1 "full endpoint catalog" (23 mocked GET
    # endpoints, see odd/tasks/datev-mock-admin-ui-polish.md) — proportional
    # per the task doc's testing rationale: proves the catalog was actually
    # built and references real paths, without asserting exact HTML
    # structure (which would be brittle).
    body = client.get(ADMIN_PAGE).text
    for representative_path_fragment in ("addressees", "fiscal-years", "domains"):
        assert representative_path_fragment in body


def test_admin_page_references_highlight_js_cdn(client):
    # Smoke test for the catalog's "View sample data" Table/Raw tabs
    # follow-on: the Raw tab syntax-highlights the response body via
    # highlight.js loaded from cdnjs, proportional per this project's
    # testing rationale for presentational admin-page work.
    body = client.get(ADMIN_PAGE).text
    assert "cdnjs.cloudflare.com/ajax/libs/highlight.js/" in body
    assert "highlight.min.js" in body


def test_admin_page_catalog_sample_area_uses_bootstrap_tabs(client):
    # Confirms the catalog-rendering JS builds a Table/Raw tabbed view
    # (Bootstrap nav-tabs/tab-pane) instead of the old single-view render,
    # without asserting exact markup.
    body = client.get(ADMIN_PAGE).text
    assert "nav-tabs" in body
    assert "tab-pane" in body


def test_admin_page_catalog_still_intact_after_tabbed_sample_view(client):
    # The tabbed Table/Raw rendering change must not have broken the
    # underlying catalog itself — same evidence as
    # test_admin_page_contains_full_endpoint_catalog_sample, kept separate
    # so a regression here is attributable to this follow-on change.
    body = client.get(ADMIN_PAGE).text
    for representative_path_fragment in ("addressees", "fiscal-years", "domains"):
        assert representative_path_fragment in body


# --- stored records (P2 of
# datev-mock-write-endpoints-and-observability.md: SQLite-backed write
# endpoints, admin UI visibility for what's been POSTed/PUT) ---


def test_stored_records_endpoint_returns_empty_list_by_default(client):
    response = client.get(STORED_RECORDS_ENDPOINT)
    assert response.status_code == 200
    assert response.json() == []


def test_stored_records_endpoint_reflects_a_written_debitor(client):
    fiscal_year_url = (
        "/datev/api/accounting/v1/clients/example-client-id/"
        "fiscal-years/example-fiscal-year-id/debitors"
    )
    created = client.post(fiscal_year_url, json={"caption": "Stored-records smoke test"}).json()

    rows = client.get(STORED_RECORDS_ENDPOINT).json()
    matches = [r for r in rows if r["resource_type"] == "accounting.debitors"]
    assert matches, "expected the posted debitor to appear in the stored-records listing"
    assert matches[0]["record_id"] == created["id"]
    assert matches[0]["data"]["caption"] == "Stored-records smoke test"
    assert "created_at" in matches[0] and "updated_at" in matches[0]


def test_admin_page_contains_stored_records_card(client):
    body = client.get(ADMIN_PAGE).text
    assert "Stored records" in body
    assert STORED_RECORDS_ENDPOINT in body


# --- settings ---


def test_get_settings_returns_defaults(client):
    response = client.get(SETTINGS_ENDPOINT)
    assert response.status_code == 200

    body = response.json()
    assert body["port"] == DEFAULT_PORT
    assert body["default_accounting_format"] == DEFAULT_FORMAT
    assert body["datev_api_version"] == "legacy"


def test_put_settings_changing_api_version_takes_effect_immediately(client):
    """`datev_api_version` (epic `datev-mock-expand-nested-content`
    follow-up) round-trips through the same admin settings endpoint as
    `default_accounting_format`, with the same "no restart needed"
    behavior — it's read fresh on every `cost-centers` request, not cached
    at process startup."""
    response = client.put(
        SETTINGS_ENDPOINT,
        json={
            "port": DEFAULT_PORT,
            "default_accounting_format": DEFAULT_FORMAT,
            "datev_api_version": "modern",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["datev_api_version"] == "modern"
    assert body["restart_required"] is False


def test_put_settings_changing_port_signals_restart_required(client):
    response = client.put(
        SETTINGS_ENDPOINT, json={"port": 9999, "default_accounting_format": DEFAULT_FORMAT}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["port"] == 9999
    assert body["restart_required"] is True


def test_put_settings_changing_format_takes_effect_immediately(client):
    response = client.put(
        SETTINGS_ENDPOINT, json={"port": DEFAULT_PORT, "default_accounting_format": "json"}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["default_accounting_format"] == "json"
    assert body["restart_required"] is False

    # Ambiguous/no Accept header must now resolve to the newly-set default.
    accounting_response = client.get(ACCOUNTING_CLIENTS_ENDPOINT)
    assert accounting_response.headers["content-type"].startswith("application/json")


def test_put_settings_format_only_change_does_not_flag_restart(client):
    # Change port once, then only the format in a second call: the second
    # call's restart_required must reflect that this specific call's port
    # (9999) is unchanged from what's already live, not "was ever changed".
    client.put(SETTINGS_ENDPOINT, json={"port": 9999, "default_accounting_format": DEFAULT_FORMAT})

    response = client.put(SETTINGS_ENDPOINT, json={"port": 9999, "default_accounting_format": "json"})

    assert response.json()["restart_required"] is False


def test_put_settings_invalid_port_is_rejected_and_does_not_change_state(client):
    response = client.put(
        SETTINGS_ENDPOINT, json={"port": 0, "default_accounting_format": DEFAULT_FORMAT}
    )
    assert 400 <= response.status_code < 500

    unchanged = client.get(SETTINGS_ENDPOINT).json()
    assert unchanged["port"] == DEFAULT_PORT


def test_put_settings_invalid_format_is_rejected_and_does_not_change_state(client):
    response = client.put(
        SETTINGS_ENDPOINT, json={"port": DEFAULT_PORT, "default_accounting_format": "yaml"}
    )
    assert 400 <= response.status_code < 500

    unchanged = client.get(SETTINGS_ENDPOINT).json()
    assert unchanged["default_accounting_format"] == DEFAULT_FORMAT


# --- master-data CRUD ---


def test_get_master_data_returns_current_list(client):
    response = client.get(MASTER_DATA_ENDPOINT)
    assert response.status_code == 200

    records = response.json()
    assert isinstance(records, list)
    assert len(records) == MASTER_DATA_COUNT
    assert "Id" in records[0] and "Name" in records[0]


def test_post_master_data_creates_record_with_generated_id(client):
    payload = {"Name": "Testfirma GmbH", "Number": 9999, "Status": "active", "Type": "legal_person"}

    response = client.post(MASTER_DATA_ENDPOINT, json=payload)
    assert response.status_code in (200, 201)

    created = response.json()
    assert created["Id"]
    assert created["Name"] == "Testfirma GmbH"

    listing = client.get(MASTER_DATA_ENDPOINT).json()
    assert any(r["Id"] == created["Id"] for r in listing)
    assert len(listing) == MASTER_DATA_COUNT + 1


def test_put_master_data_updates_existing_record(client):
    existing = client.get(MASTER_DATA_ENDPOINT).json()[0]

    response = client.put(f"{MASTER_DATA_ENDPOINT}/{existing['Id']}", json={"Name": "Renamed GmbH"})
    assert response.status_code == 200
    assert response.json()["Name"] == "Renamed GmbH"


def test_put_master_data_unknown_id_returns_404(client):
    response = client.put(f"{MASTER_DATA_ENDPOINT}/does-not-exist", json={"Name": "X"})
    assert response.status_code == 404


def test_delete_master_data_removes_record(client):
    existing = client.get(MASTER_DATA_ENDPOINT).json()[0]

    response = client.delete(f"{MASTER_DATA_ENDPOINT}/{existing['Id']}")
    assert response.status_code == 200

    listing = client.get(MASTER_DATA_ENDPOINT).json()
    assert all(r["Id"] != existing["Id"] for r in listing)
    assert len(listing) == MASTER_DATA_COUNT - 1


# --- accounting CRUD ---


def test_get_accounting_clients_admin_returns_current_list(client):
    response = client.get(ACCOUNTING_ENDPOINT)
    assert response.status_code == 200

    records = response.json()
    assert isinstance(records, list)
    assert len(records) == ACCOUNTING_COUNT
    assert "Id" in records[0] and "Name" in records[0]


def test_post_accounting_client_creates_record_with_generated_id(client):
    payload = {"Name": "Testkunde AG", "Number": 88888}

    response = client.post(ACCOUNTING_ENDPOINT, json=payload)
    assert response.status_code in (200, 201)

    created = response.json()
    assert created["Id"]
    assert created["Name"] == "Testkunde AG"

    listing = client.get(ACCOUNTING_ENDPOINT).json()
    assert any(r["Id"] == created["Id"] for r in listing)
    assert len(listing) == ACCOUNTING_COUNT + 1


def test_put_accounting_client_updates_existing_record(client):
    existing = client.get(ACCOUNTING_ENDPOINT).json()[0]

    response = client.put(f"{ACCOUNTING_ENDPOINT}/{existing['Id']}", json={"Name": "Renamed AG"})
    assert response.status_code == 200
    assert response.json()["Name"] == "Renamed AG"


def test_put_accounting_client_unknown_id_returns_404(client):
    response = client.put(f"{ACCOUNTING_ENDPOINT}/does-not-exist", json={"Name": "X"})
    assert response.status_code == 404


def test_delete_accounting_client_removes_record(client):
    existing = client.get(ACCOUNTING_ENDPOINT).json()[0]

    response = client.delete(f"{ACCOUNTING_ENDPOINT}/{existing['Id']}")
    assert response.status_code == 200

    listing = client.get(ACCOUNTING_ENDPOINT).json()
    assert all(r["Id"] != existing["Id"] for r in listing)
    assert len(listing) == ACCOUNTING_COUNT - 1


# --- reset ---


def test_reset_restores_both_datasets_to_original_cardinality(client):
    client.post(
        MASTER_DATA_ENDPOINT,
        json={"Name": "Extra", "Number": 1, "Status": "active", "Type": "legal_person"},
    )
    client.post(ACCOUNTING_ENDPOINT, json={"Name": "Extra", "Number": 1})

    response = client.post(RESET_ENDPOINT)
    assert response.status_code == 200

    assert len(client.get(MASTER_DATA_ENDPOINT).json()) == MASTER_DATA_COUNT
    assert len(client.get(ACCOUNTING_ENDPOINT).json()) == ACCOUNTING_COUNT


# --- follow-on: /docs link, per-card endpoint display, DATEV doc links ---
# Smoke tests for the datev-mock-admin-ui-polish.md "Follow-on" section
# (U5/U6) — proportional, presentational-only additions, same rationale as
# the U1 smoke tests above: prove the additions actually landed in the
# rendered page, without asserting exact HTML structure.


def test_admin_page_links_to_swagger_docs(client):
    body = client.get(ADMIN_PAGE).text
    assert '/docs"' in body


def test_admin_page_contains_confirmed_datev_documentation_urls(client):
    body = client.get(ADMIN_PAGE).text
    assert (
        "https://developer.datev.de/de/product-detail/client-master-data/1.7.0/"
        "reference/reference-overview/client-master-data"
    ) in body
    assert (
        "https://developer.datev.de/de/product-detail/accounting/1.7.4/"
        "reference/reference-overview/accounting"
    ) in body


def test_admin_page_shows_real_endpoint_on_master_data_and_accounting_cards(client):
    body = client.get(ADMIN_PAGE).text
    assert "master-data/v1/clients" in body
    assert "accounting/v1/clients" in body


# --- follow-on: V4 "Custom Examples (Overrides)" card ---
# Proportional smoke tests confirming the new upload/resolve/toggle/delete UI
# section actually landed in the rendered page and wires up against the
# `/admin/api/overrides*` contract (see
# odd/tasks/datev-mock-custom-overrides.md V4) — reasonable substring checks,
# not brittle exact-markup assertions.


def test_admin_page_contains_overrides_card_heading(client):
    body = client.get(ADMIN_PAGE).text
    assert "Custom Examples" in body
    assert 'id="overrides-card"' in body


def test_admin_page_references_overrides_upload_endpoint(client):
    body = client.get(ADMIN_PAGE).text
    assert "/admin/api/overrides" in body


def test_admin_page_references_overrides_resolve_toggle_delete_patterns(client):
    body = client.get(ADMIN_PAGE).text
    assert "/admin/api/overrides/resolve" in body
    assert "method: \"PUT\"" in body
    assert "method: \"DELETE\"" in body


# --- follow-on: CSV export/import for both CRUD tables + override endpoint
# URL display --- proportional smoke tests confirming the additions actually
# landed in the rendered page (presentational/client-side work — see the
# rationale on the smoke tests above).


def test_admin_page_has_csv_export_buttons_for_both_tables(client):
    body = client.get(ADMIN_PAGE).text
    assert 'id="md-export-csv"' in body
    assert 'id="ac-export-csv"' in body
    assert "Export CSV" in body


def test_admin_page_has_csv_import_controls_for_both_tables(client):
    body = client.get(ADMIN_PAGE).text
    assert 'id="md-import-file"' in body
    assert 'id="md-import-btn"' in body
    assert 'id="ac-import-file"' in body
    assert 'id="ac-import-btn"' in body
    assert "Import CSV" in body


def test_admin_page_embeds_csv_helper_functions(client):
    body = client.get(ADMIN_PAGE).text
    assert "function toCsv(" in body
    assert "function fromCsv(" in body


def test_admin_page_embeds_override_endpoint_paths_mapping(client):
    body = client.get(ADMIN_PAGE).text
    assert "OVERRIDE_ENDPOINT_PATHS" in body
    # A known real path from the mapping, distinct from CATALOG's own
    # occurrence of the same path (banks has no dedicated CATALOG-only
    # wording, so also assert the JS constant name is actually present).
    assert "/datev/api/master-data/v1/banks" in body


# --- follow-on: XML Table tab support + bulk folder import for overrides ---
# Proportional smoke tests confirming both additions actually landed in the
# rendered page (presentational/client-side work — same rationale as the
# smoke tests above): the XML-to-table conversion function is present (proof
# it was actually added, not just that the page still loads), and the folder
# import control/label are present.


def test_admin_page_contains_xml_table_conversion_function(client):
    body = client.get(ADMIN_PAGE).text
    assert "function xmlToRecords(" in body
    assert "function parseXmlForTable(" in body


def test_admin_page_has_folder_import_control(client):
    body = client.get(ADMIN_PAGE).text
    assert 'id="override-folder-input"' in body
    assert "webkitdirectory" in body
    assert 'id="override-folder-import-btn"' in body
    assert "Import Folder" in body
