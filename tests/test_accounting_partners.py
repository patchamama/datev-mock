"""RED-phase tests for the Accounting business-partner endpoints (epic
`datev-mock-extended-endpoints`, Phase B, batch B1).

Covers 2 of the 15 target endpoints:
  - `GET .../fiscal-years/{fiscal-year-id}/creditors` (compiled spec doc #10)
  - `GET .../fiscal-years/{fiscal-year-id}/debitors` (compiled spec doc #11)

Ground truth: the compiled OpenAPI reference written to the session
scratchpad's `datev-endpoint-specs.md`, plus the cross-phase decisions in
`odd/tasks/datev-mock-extended-endpoints.md`:

- JSON-only bare arrays, no pagination wrapper.
- `{client-id}` / `{fiscal-year-id}` path params never filter the dataset —
  tested explicitly below, not just documented.
- `creditor`/`debitor` use the exact same "no real OpenAPI polymorphism"
  pattern already established for `Addressee` in Phase A: a flat
  `legal_entity_type` enum (`not_specified`/`natural_person`/`legal_person`)
  plus co-located, optional `natural_person`/`legal_person`/
  `not_specified_person` sibling objects, gated only by description text.
  This suite mirrors Phase A's "both types present, type-specific fields
  populated" test pattern for that same reason.
- `debitor` is structurally identical to `creditor` except for a richer
  `accounting_information` sub-schema (dunning/credit-limit/direct-debit
  fields) — this suite does not re-assert every one of debitor's ~30 extra
  `accounting_information` fields, only the shared top-level contract
  (judgment call, see progress entry).

These tests intentionally import `CREDITORS_ENDPOINT` / `DEBITORS_ENDPOINT`
directly from `app.routers.accounting`, which do not exist yet. This import
is expected to fail at collection time (`ImportError`) until the GREEN-phase
router work (tasks B1/B2-GREEN) adds these endpoints and their constants —
that failure is the correct RED signal for this task; do not add a
try/except around it to hide it.
"""
from __future__ import annotations

import uuid

from app.routers.accounting import CREDITORS_ENDPOINT, DEBITORS_ENDPOINT

MIN_CREDITORS = 3
MIN_DEBITORS = 3

_LEGAL_ENTITY_TYPE_VALUES = {"not_specified", "natural_person", "legal_person"}


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get(client, endpoint_template: str, client_id: str | None = None, fiscal_year_id: str | None = None) -> list[dict]:
    response = client.get(
        endpoint_template.format(
            client_id=client_id or _fresh_id(), fiscal_year_id=fiscal_year_id or _fresh_id()
        )
    )
    return response.json()


def _assert_business_partner_core_fields(record: dict) -> None:
    assert isinstance(record.get("id"), str) and record["id"].strip()
    assert isinstance(record.get("account_number"), int)
    assert isinstance(record.get("addressee_id"), str) and record["addressee_id"].strip()
    assert isinstance(record.get("business_partner_number"), str) and record["business_partner_number"].strip()
    assert record.get("legal_entity_type") in _LEGAL_ENTITY_TYPE_VALUES
    assert isinstance(record.get("short_name"), str) and record["short_name"].strip()


# --- GET .../fiscal-years/{fiscal-year-id}/creditors ---


def test_creditors_returns_200_json_array_with_minimum_records(client):
    response = client.get(CREDITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_CREDITORS, (
        f"expected at least {MIN_CREDITORS} creditor records, got {len(records)}"
    )


def test_creditor_record_has_core_fields(client):
    records = _get(client, CREDITORS_ENDPOINT)
    assert records, "no creditor records returned"

    for record in records:
        _assert_business_partner_core_fields(record)


def test_creditor_dataset_contains_both_natural_and_legal_person_types(client):
    """Mirrors Phase A's addressee-dataset test: proves the fake dataset
    actually varies `legal_entity_type`, not just declares the enum."""
    records = _get(client, CREDITORS_ENDPOINT)
    types_seen = {record.get("legal_entity_type") for record in records}
    assert {"natural_person", "legal_person"} <= types_seen, (
        f"expected both natural_person and legal_person creditors, saw {types_seen}"
    )


def test_natural_person_creditors_have_representative_fields(client):
    records = _get(client, CREDITORS_ENDPOINT)
    natural_person_records = [r for r in records if r.get("legal_entity_type") == "natural_person"]
    assert natural_person_records, "no natural_person creditor records returned"

    for record in natural_person_records:
        natural_person = record.get("natural_person")
        assert isinstance(natural_person, dict)
        assert isinstance(natural_person.get("firstname"), str) and natural_person["firstname"].strip()
        assert isinstance(natural_person.get("surname"), str) and natural_person["surname"].strip()


def test_legal_person_creditors_have_representative_fields(client):
    records = _get(client, CREDITORS_ENDPOINT)
    legal_person_records = [r for r in records if r.get("legal_entity_type") == "legal_person"]
    assert legal_person_records, "no legal_person creditor records returned"

    for record in legal_person_records:
        legal_person = record.get("legal_person")
        assert isinstance(legal_person, dict)
        assert isinstance(legal_person.get("legal_name"), str) and legal_person["legal_name"].strip()


def test_creditors_ignores_path_param_values(client):
    first = _get(client, CREDITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get(client, CREDITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/debitors ---


def test_debitors_returns_200_json_array_with_minimum_records(client):
    response = client.get(DEBITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_DEBITORS, (
        f"expected at least {MIN_DEBITORS} debitor records, got {len(records)}"
    )


def test_debitor_record_has_core_fields(client):
    records = _get(client, DEBITORS_ENDPOINT)
    assert records, "no debitor records returned"

    for record in records:
        _assert_business_partner_core_fields(record)


def test_debitor_dataset_contains_both_natural_and_legal_person_types(client):
    records = _get(client, DEBITORS_ENDPOINT)
    types_seen = {record.get("legal_entity_type") for record in records}
    assert {"natural_person", "legal_person"} <= types_seen, (
        f"expected both natural_person and legal_person debitors, saw {types_seen}"
    )


def test_debitors_ignores_path_param_values(client):
    first = _get(client, DEBITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get(client, DEBITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second
