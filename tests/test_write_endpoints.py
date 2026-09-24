"""RED-phase tests for P2's 15 new write ("POST"/"PUT") endpoints across
`app/routers/accounting.py` and `app/routers/master_data.py` (see
odd/tasks/datev-mock-write-endpoints-and-observability.md, "Group A"):
debitors, creditors, terms-of-payment, asset stocktaking, cost-centers,
master-data clients (+ responsibilities), master-data addressees.

These tests import endpoint constants that don't exist yet on the accounting
and master_data routers (`DEBITOR_ENDPOINT`, `CLIENT_BY_ID_ENDPOINT`, etc.) --
expected to fail at collection time until the GREEN-phase router work lands,
same precedent as `tests/test_accounting_partners.py`.

Not every one of the 15 routes gets its own dedicated test -- debitors,
creditors, terms-of-payment, cost-centers, and master-data clients are
covered individually (including the GET-merges-SQLite round trip, in both
JSON and XML where that endpoint supports XML); asset stocktaking,
responsibilities, and addressees get a smaller, representative smoke test
each, consistent with this project's existing "don't re-assert every field
of a structurally-identical sibling" judgment call (see
`tests/test_accounting_partners.py`'s own module docstring).
"""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET

from app.routers.accounting import (
    ASSET_STOCKTAKING_ENDPOINT,
    COST_CENTERS_ENDPOINT,
    CREDITORS_ENDPOINT,
    DEBITORS_ENDPOINT,
    TERMS_OF_PAYMENT_ENDPOINT,
)
from app.routers.master_data import (
    ADDRESSEES_ENDPOINT,
    EMPLOYEES_ENDPOINT,
    ENDPOINT as CLIENTS_ENDPOINT,
)

JSON_ACCEPT_HEADERS = {"accept": "application/json"}
XML_ACCEPT_HEADERS = {"accept": "application/xml"}


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _fiscal_year_url(template: str) -> str:
    return template.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())


def _cost_system_url(template: str) -> str:
    return template.format(
        client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
    )


def _asset_stocktaking_url() -> str:
    return ASSET_STOCKTAKING_ENDPOINT.format(
        client_id=_fresh_id(), fiscal_year_id=_fresh_id(), asset_id=_fresh_id()
    )


# --- debitors ---


def test_post_debitor_generates_id_and_stores_record(client):
    url = _fiscal_year_url(DEBITORS_ENDPOINT)
    resp = client.post(url, json={"caption": "Acme Debitor", "short_name": "Acme"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["caption"] == "Acme Debitor"
    assert body["id"]  # server-generated


def test_put_debitor_by_id_uses_given_id(client):
    debitor_id = _fresh_id()
    url = _fiscal_year_url(DEBITORS_ENDPOINT) + f"/{debitor_id}"
    resp = client.put(url, json={"caption": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["id"] == debitor_id


def test_put_debitors_list_stores_every_item(client):
    url = _fiscal_year_url(DEBITORS_ENDPOINT)
    resp = client.put(url, json=[{"caption": "One"}, {"caption": "Two"}])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {item["caption"] for item in body} == {"One", "Two"}


def test_posted_debitor_appears_in_get_json_and_xml(client):
    post_url = _fiscal_year_url(DEBITORS_ENDPOINT)
    caption = f"Round-trip Debitor {_fresh_id()}"
    created = client.post(post_url, json={"caption": caption, "short_name": "RT"}).json()

    json_resp = client.get(post_url, headers=JSON_ACCEPT_HEADERS)
    ids = [r["id"] for r in json_resp.json()]
    assert created["id"] in ids

    xml_resp = client.get(post_url, headers=XML_ACCEPT_HEADERS)
    assert created["id"] in xml_resp.text


# --- creditors ---


def test_post_creditor_generates_id_and_stores_record(client):
    url = _fiscal_year_url(CREDITORS_ENDPOINT)
    resp = client.post(url, json={"caption": "Acme Creditor"})
    assert resp.status_code == 201
    assert resp.json()["caption"] == "Acme Creditor"


def test_posted_creditor_appears_in_get_json_and_xml(client):
    post_url = _fiscal_year_url(CREDITORS_ENDPOINT)
    caption = f"Round-trip Creditor {_fresh_id()}"
    created = client.post(post_url, json={"caption": caption}).json()

    json_resp = client.get(post_url, headers=JSON_ACCEPT_HEADERS)
    ids = [r["id"] for r in json_resp.json()]
    assert created["id"] in ids

    xml_resp = client.get(post_url, headers=XML_ACCEPT_HEADERS)
    root = ET.fromstring(xml_resp.content)
    assert root is not None  # well-formed even with a written record present
    assert created["id"] in xml_resp.text


def test_posted_creditor_is_scoped_to_its_fiscal_year_only(client):
    """New cross-reference coverage (decision #7): SQLite scoping
    isolation -- a creditor POSTed under one (client_id, fiscal_year_id)
    must not appear in GET creditors for a *different* fiscal_year_id under
    the same client_id, proving app.db's scope-forwarding (architecture
    decision #5) actually isolates SQLite-stored records per scope, not
    just per client."""
    client_id = _fresh_id()
    fiscal_year_id_a = _fresh_id()
    fiscal_year_id_b = _fresh_id()
    caption = f"Scoped Creditor {_fresh_id()}"

    post_url = CREDITORS_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id_a)
    created = client.post(post_url, json={"caption": caption}).json()

    other_scope_url = CREDITORS_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id_b)
    other_scope_ids = [
        r["id"] for r in client.get(other_scope_url, headers=JSON_ACCEPT_HEADERS).json()
    ]
    assert created["id"] not in other_scope_ids


# --- terms-of-payment ---


def test_post_term_of_payment_requires_caption(client):
    url = _fiscal_year_url(TERMS_OF_PAYMENT_ENDPOINT)
    resp = client.post(url, json={})
    assert resp.status_code == 422


def test_post_term_of_payment_creates_record(client):
    url = _fiscal_year_url(TERMS_OF_PAYMENT_ENDPOINT)
    resp = client.post(url, json={"caption": "Net 30"})
    assert resp.status_code == 201
    assert resp.json()["caption"] == "Net 30"


def test_put_term_of_payment_by_id(client):
    term_id = _fresh_id()
    url = _fiscal_year_url(TERMS_OF_PAYMENT_ENDPOINT) + f"/{term_id}"
    resp = client.put(url, json={"caption": "Net 60"})
    assert resp.status_code == 200
    assert resp.json()["id"] == term_id


# --- asset stocktaking ---


def test_put_asset_stocktaking_requires_asset_number_and_inventory_number(client):
    resp = client.put(_asset_stocktaking_url(), json={})
    assert resp.status_code == 422


def test_put_asset_stocktaking_stores_extended_write_only_fields(client):
    resp = client.put(
        _asset_stocktaking_url(),
        json={
            "asset_number": 42,
            "inventory_number": "INV-1",
            "acquisition_date": "2020-01-01",
            "economic_lifetime": 5,
            "isin": "DE000A1EWWW0",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["acquisition_date"] == "2020-01-01"
    assert body["economic_lifetime"] == 5
    assert body["isin"] == "DE000A1EWWW0"


# --- cost centers ---


def test_put_cost_center_by_id_stores_new_write_fields(client):
    cost_center_id = _fresh_id()
    url = _cost_system_url(COST_CENTERS_ENDPOINT) + f"/{cost_center_id}"
    resp = client.put(
        url,
        json={
            "long_name": "Marketing",
            "short_name": "MKT",
            "email": "mkt@example.com",
            "note": "note text",
            "postable_from": "2024-01-01",
            "postable_to": "2024-12-31",
            "reference_value": "REF-1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == cost_center_id
    assert body["email"] == "mkt@example.com"


def test_posted_cost_center_appears_in_get_json_and_xml(client):
    cost_center_id = _fresh_id()
    list_url = _cost_system_url(COST_CENTERS_ENDPOINT)
    put_url = f"{list_url}/{cost_center_id}"
    client.put(put_url, json={"long_name": "Sales", "short_name": "SLS"})

    json_resp = client.get(list_url, headers=JSON_ACCEPT_HEADERS)
    ids = [r["id"] for r in json_resp.json()]
    assert cost_center_id in ids

    xml_resp = client.get(list_url, headers=XML_ACCEPT_HEADERS)
    assert cost_center_id in xml_resp.text


# --- master-data clients ---


def test_post_client_requires_name_number_and_type(client):
    resp = client.post(CLIENTS_ENDPOINT, json={})
    assert resp.status_code == 422


def test_post_client_creates_record(client):
    resp = client.post(
        CLIENTS_ENDPOINT, json={"name": "New Client", "number": 999001, "type": "legal_person"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "New Client"
    assert body["id"]


def test_posted_client_appears_in_get_json_and_xml(client):
    unique_number = 999002
    created = client.post(
        CLIENTS_ENDPOINT,
        json={"name": "Round-trip Client", "number": unique_number, "type": "legal_person"},
    ).json()

    json_resp = client.get(CLIENTS_ENDPOINT, headers=JSON_ACCEPT_HEADERS)
    ids = [r["id"] for r in json_resp.json()]
    assert created["id"] in ids

    xml_resp = client.get(CLIENTS_ENDPOINT, headers=XML_ACCEPT_HEADERS)
    assert created["id"] in xml_resp.text


def test_put_client_responsibilities_rejects_unknown_employee_id(client):
    """P3 (odd/tasks/datev-mock-referential-integrity.md, decision #7):
    replaces the old *_stores_array_without_validating_employee test, which
    encoded the pre-P2 lack of FK validation. An employee_id that resolves
    to no real record (neither the fake dataset -- there is none, master
    data employees are SQLite-only -- nor anything POSTed) must 422."""
    client_id = _fresh_id()
    url = f"{CLIENTS_ENDPOINT}/{client_id}/responsibilities"
    resp = client.put(
        url,
        json=[
            {"employee_id": "does-not-exist-yet", "area_of_responsibility_name": "Payroll"},
        ],
    )
    assert resp.status_code == 422


def test_put_client_responsibilities_accepts_real_employee_id(client):
    """Companion happy-path test: an employee_id fetched from a real POST
    to the employees endpoint must be accepted (P2's write-side FK
    validation, architecture decision #6)."""
    employee = client.post(
        EMPLOYEES_ENDPOINT, json={"name": "Jane Payroll", "natural_person_id": _fresh_id()}
    ).json()

    client_id = _fresh_id()
    url = f"{CLIENTS_ENDPOINT}/{client_id}/responsibilities"
    resp = client.put(
        url,
        json=[
            {"employee_id": employee["id"], "area_of_responsibility_name": "Payroll"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["employee_id"] == employee["id"]


def test_put_client_responsibilities_replaces_prior_list(client):
    client_id = _fresh_id()
    url = f"{CLIENTS_ENDPOINT}/{client_id}/responsibilities"
    client.put(url, json=[{"area_of_responsibility_name": "First"}])
    resp = client.put(url, json=[{"area_of_responsibility_name": "Second"}])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["area_of_responsibility_name"] == "Second"


# --- master-data addressees ---


def test_post_addressee_requires_type(client):
    resp = client.post(ADDRESSEES_ENDPOINT, json={})
    assert resp.status_code == 422


def test_posted_addressee_appears_in_get(client):
    created = client.post(
        ADDRESSEES_ENDPOINT, json={"type": "legal_person", "current_short_name": "RTAddr"}
    ).json()
    ids = [r["id"] for r in client.get(ADDRESSEES_ENDPOINT).json()]
    assert created["id"] in ids


def test_put_addressee_by_id_uses_given_id(client):
    addressee_id = _fresh_id()
    url = f"{ADDRESSEES_ENDPOINT}/{addressee_id}"
    resp = client.put(url, json={"type": "natural_person"})
    assert resp.status_code == 200
    assert resp.json()["id"] == addressee_id
