"""RED-phase tests for P3's Group B write endpoints -- 7 brand-new resource
families with no prior GET modeling at all (see
odd/tasks/datev-mock-write-endpoints-and-observability.md, "Group B"):
cost-center-properties, cost-sequences (+ cost-accounting-records),
various-addresses, employees, internal-cost-services, accounting-sequences
(create), posting-proposals batch (incoming/outgoing/cash-register).

These tests import endpoint constants that don't exist yet on the accounting
and master_data routers -- expected to fail at collection time until the
GREEN-phase router work lands, same precedent as `tests/test_write_endpoints.py`.

11 of the 16 operations have a matching GET (round-trip tested here, same
"POST/PUT then GET" pattern as Group A); the 5 create-only operations
(internal-cost-services, accounting-sequences, the 3 posting-proposals
batches) have no GET route at all per the spec -- verified instead via
`app.db.get_record`/`list_records` directly (the admin UI's "Stored records"
card's own data source) and via a 405 (Method Not Allowed) on any GET
attempt to that same path -- the path is registered for POST, so
FastAPI/Starlette correctly answers 405, not a route-unmatched 404 (see
`app/request_log.py`'s own unmatched-vs-legitimate-404 distinction from P1 --
a 405 here is neither).
"""
from __future__ import annotations

import uuid

from app import db
from app.routers.accounting import (
    ACCOUNTING_SEQUENCES_ENDPOINT,
    COST_CENTER_PROPERTIES_ENDPOINT,
    COST_SEQUENCES_ENDPOINT,
    INTERNAL_COST_SERVICES_ENDPOINT,
    POSTING_PROPOSALS_CASH_REGISTER_BATCH_ENDPOINT,
    POSTING_PROPOSALS_INCOMING_INVOICES_BATCH_ENDPOINT,
    POSTING_PROPOSALS_OUTGOING_INVOICES_BATCH_ENDPOINT,
    VARIOUS_ADDRESSES_ENDPOINT,
)
from app.routers.master_data import EMPLOYEES_ENDPOINT

JSON_ACCEPT_HEADERS = {"accept": "application/json"}


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _fiscal_year_url(template: str) -> str:
    return template.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())


def _cost_system_url(template: str) -> str:
    return template.format(
        client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
    )


# --- cost-center-properties (PUT by id, list GET) ---


def test_put_cost_center_property_by_id_uses_given_id(client):
    property_id = _fresh_id()
    url = _cost_system_url(COST_CENTER_PROPERTIES_ENDPOINT) + f"/{property_id}"
    resp = client.put(url, json={"description": "Region"})
    assert resp.status_code == 200
    assert resp.json()["id"] == property_id


def test_posted_cost_center_property_appears_in_get(client):
    property_id = _fresh_id()
    list_url = _cost_system_url(COST_CENTER_PROPERTIES_ENDPOINT)
    client.put(f"{list_url}/{property_id}", json={"description": "Region"})

    resp = client.get(list_url, headers=JSON_ACCEPT_HEADERS)
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert property_id in ids


# --- cost-sequences (PUT by id, required id+month, list GET) ---


def test_put_cost_sequence_requires_id_and_month_in_body(client):
    cost_sequence_id = _fresh_id()
    url = _cost_system_url(COST_SEQUENCES_ENDPOINT) + f"/{cost_sequence_id}"
    resp = client.put(url, json={})
    assert resp.status_code == 422


def test_posted_cost_sequence_appears_in_get(client):
    cost_sequence_id = _fresh_id()
    list_url = _cost_system_url(COST_SEQUENCES_ENDPOINT)
    put_url = f"{list_url}/{cost_sequence_id}"
    resp = client.put(put_url, json={"id": cost_sequence_id, "month": 3})
    assert resp.status_code == 200
    assert resp.json()["id"] == cost_sequence_id

    get_resp = client.get(list_url, headers=JSON_ACCEPT_HEADERS)
    ids = [r["id"] for r in get_resp.json()]
    assert cost_sequence_id in ids


# --- cost-accounting-records (POST, required account_number+date, list GET) ---


def test_post_cost_accounting_record_requires_account_number_and_date(client):
    cost_sequence_id = _fresh_id()
    url = _cost_system_url(COST_SEQUENCES_ENDPOINT) + f"/{cost_sequence_id}/cost-accounting-records"
    resp = client.post(url, json={})
    assert resp.status_code == 422


def test_posted_cost_accounting_record_appears_in_get(client):
    cost_sequence_id = _fresh_id()
    url = _cost_system_url(COST_SEQUENCES_ENDPOINT) + f"/{cost_sequence_id}/cost-accounting-records"
    created = client.post(url, json={"account_number": 4200, "date": "2024-05-01"}).json()
    assert created["id"]

    get_resp = client.get(url, headers=JSON_ACCEPT_HEADERS)
    assert get_resp.status_code == 200
    ids = [r["id"] for r in get_resp.json()]
    assert created["id"] in ids


# --- various-addresses (POST, list GET) ---


def test_posted_various_address_appears_in_get(client):
    url = _fiscal_year_url(VARIOUS_ADDRESSES_ENDPOINT)
    created = client.post(url, json={"caption": "Warehouse", "short_name": "WH"}).json()
    assert created["id"]

    get_resp = client.get(url, headers=JSON_ACCEPT_HEADERS)
    assert get_resp.status_code == 200
    ids = [r["id"] for r in get_resp.json()]
    assert created["id"] in ids


# --- employees (POST/PUT, list + by-id GET) ---


def test_post_employee_requires_name_and_natural_person_id(client):
    resp = client.post(EMPLOYEES_ENDPOINT, json={})
    assert resp.status_code == 422


def test_posted_employee_appears_in_get_list_and_by_id(client):
    created = client.post(
        EMPLOYEES_ENDPOINT, json={"name": "Jane Doe", "natural_person_id": _fresh_id()}
    ).json()
    assert created["id"]

    list_resp = client.get(EMPLOYEES_ENDPOINT)
    ids = [r["id"] for r in list_resp.json()]
    assert created["id"] in ids

    by_id_resp = client.get(f"{EMPLOYEES_ENDPOINT}/{created['id']}")
    assert by_id_resp.status_code == 200
    assert by_id_resp.json()["id"] == created["id"]


def test_get_employee_by_id_404_for_unknown_id(client):
    resp = client.get(f"{EMPLOYEES_ENDPOINT}/does-not-exist")
    assert resp.status_code == 404


def test_put_employee_by_id_uses_given_id(client):
    employee_id = _fresh_id()
    url = f"{EMPLOYEES_ENDPOINT}/{employee_id}"
    resp = client.put(url, json={"name": "Renamed", "natural_person_id": _fresh_id()})
    assert resp.status_code == 200
    assert resp.json()["id"] == employee_id


# --- internal-cost-services (POST, create-only, no GET) ---


def test_post_internal_cost_service_requires_cost_center_from_to_and_month(client):
    url = _cost_system_url(INTERNAL_COST_SERVICES_ENDPOINT)
    resp = client.post(url, json={})
    assert resp.status_code == 422


def test_posted_internal_cost_service_is_stored_but_not_gettable(client):
    url = _cost_system_url(INTERNAL_COST_SERVICES_ENDPOINT)
    resp = client.post(
        url, json={"cost_center_from": "CC1", "cost_center_to": "CC2", "month": "2024-05"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]

    # No public GET route exists for this resource (spec: create-only) --
    # the path itself is registered (for POST), so FastAPI/Starlette
    # answers 405 Method Not Allowed for GET, not a route-unmatched 404.
    assert client.get(url).status_code == 405

    # But it IS visible via the generic stored-records mechanism (admin UI).
    stored = db.get_record("accounting.internal_cost_services", body["id"])
    assert stored is not None
    assert stored["cost_center_from"] == "CC1"


# --- accounting-sequences (POST, create-only, no GET) ---


def test_post_accounting_sequence_requires_date_from_and_date_to(client):
    url = _fiscal_year_url(ACCOUNTING_SEQUENCES_ENDPOINT)
    resp = client.post(url, json={})
    assert resp.status_code == 422


def test_posted_accounting_sequence_is_stored_but_not_gettable(client):
    url = _fiscal_year_url(ACCOUNTING_SEQUENCES_ENDPOINT)
    resp = client.post(url, json={"date_from": "2024-01-01", "date_to": "2024-01-31"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert client.get(url).status_code == 405

    stored = db.get_record("accounting.accounting_sequences", body["id"])
    assert stored is not None
    assert stored["date_from"] == "2024-01-01"


# --- posting-proposals batches (POST array body, create-only, no GET) ---


def test_post_posting_proposals_incoming_invoices_batch_requires_amount_and_date(client):
    url = _fiscal_year_url(POSTING_PROPOSALS_INCOMING_INVOICES_BATCH_ENDPOINT)
    resp = client.post(url, json=[{}])
    assert resp.status_code == 422


def test_posted_posting_proposals_incoming_invoices_batch_is_stored(client):
    url = _fiscal_year_url(POSTING_PROPOSALS_INCOMING_INVOICES_BATCH_ENDPOINT)
    resp = client.post(
        url,
        json=[
            {"amount": 100.0, "date": "2024-02-01", "creditor_account_number": 70000},
            {"amount": 50.5, "date": "2024-02-02"},
        ],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 2
    assert all(item["id"] for item in body)
    assert client.get(url).status_code == 405


def test_posted_posting_proposals_outgoing_invoices_batch_is_stored(client):
    url = _fiscal_year_url(POSTING_PROPOSALS_OUTGOING_INVOICES_BATCH_ENDPOINT)
    resp = client.post(
        url, json=[{"amount": 200.0, "date": "2024-03-01", "debitor_account_number": 10000}]
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 1
    stored = db.get_record("accounting.posting_proposals_outgoing_invoices", body[0]["id"])
    assert stored["debitor_account_number"] == 10000


def test_posted_posting_proposals_cash_register_batch_is_stored(client):
    url = _fiscal_year_url(POSTING_PROPOSALS_CASH_REGISTER_BATCH_ENDPOINT)
    resp = client.post(
        url, json=[{"amount": 30.0, "cash_account_number": 1000, "date": "2024-04-01"}]
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 1
    assert client.get(url).status_code == 405


def test_post_posting_proposals_cash_register_batch_requires_cash_account_number(client):
    url = _fiscal_year_url(POSTING_PROPOSALS_CASH_REGISTER_BATCH_ENDPOINT)
    resp = client.post(url, json=[{"amount": 30.0, "date": "2024-04-01"}])
    assert resp.status_code == 422
