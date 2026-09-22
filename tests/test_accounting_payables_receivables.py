"""RED-phase tests for the Accounting open-item endpoints (epic
`datev-mock-extended-endpoints`, Phase B, batch B2).

Covers 3 of the 15 target endpoints:
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-payable` (compiled spec
    doc #6)
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-payable/condense`
    (compiled spec doc #2 — **same schema** as accounts-payable, condense is
    server-side aggregation, not a different shape)
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-receivable/condense`
    (compiled spec doc #3 — same base fields as accounts-payable plus
    `dunning_level`/`dunning_date1/2/3`, no equivalent in accounts-payable)

Ground truth: the compiled OpenAPI reference written to the session
scratchpad's `datev-endpoint-specs.md`, plus the cross-phase decisions in
`odd/tasks/datev-mock-extended-endpoints.md`:

- JSON-only bare arrays, no pagination wrapper.
- `{client-id}` / `{fiscal-year-id}` path params never filter the dataset —
  tested explicitly below, not just documented.
- `accounts-payable/condense` and `accounts-payable` share the same schema;
  this suite tests both work independently, without asserting their bodies
  are identical (per task instructions — condense is a real server-side
  aggregation in the real API, even though this mock doesn't implement
  aggregation logic).
- This mock does not implement streaming, so the streaming-only field-drop
  quirk (`open_balance_of_item`/`debit_credit_identifier` omitted when
  streamed) does not apply here — both fields are asserted present on every
  record.

These tests intentionally import `ACCOUNTS_PAYABLE_ENDPOINT` /
`ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT` / `ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT`
directly from `app.routers.accounting`, which do not exist yet. This import
is expected to fail at collection time (`ImportError`) until the GREEN-phase
router work (tasks B1/B2-GREEN) adds these endpoints and their constants —
that failure is the correct RED signal for this task; do not add a
try/except around it to hide it.
"""
from __future__ import annotations

import uuid

from app.routers.accounting import (
    ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT,
    ACCOUNTS_PAYABLE_ENDPOINT,
    ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT,
)

MIN_ACCOUNTS_PAYABLE = 3
MIN_ACCOUNTS_PAYABLE_CONDENSE = 3
MIN_ACCOUNTS_RECEIVABLE_CONDENSE = 3

_EVIDENCE_TYPE_VALUES = {
    "invoice",
    "credit_note",
    "credit_note_by_revocation",
    "deposit",
    "payment",
    "cash_discount",
}
_DEBIT_CREDIT_IDENTIFIER_VALUES = {"S", "H"}


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get(client, endpoint_template: str, client_id: str | None = None, fiscal_year_id: str | None = None) -> list[dict]:
    response = client.get(
        endpoint_template.format(
            client_id=client_id or _fresh_id(), fiscal_year_id=fiscal_year_id or _fresh_id()
        )
    )
    return response.json()


def _assert_open_item_core_fields(record: dict) -> None:
    assert isinstance(record.get("id"), str) and record["id"].strip()
    assert isinstance(record.get("account_number"), int)
    assert isinstance(record.get("amount_debit"), (int, float))
    assert isinstance(record.get("amount_credit"), (int, float))
    assert isinstance(record.get("amount_entered"), (int, float))
    assert isinstance(record.get("currency_code"), str) and record["currency_code"].strip()
    assert record.get("evidence_type") in _EVIDENCE_TYPE_VALUES
    assert record.get("debit_credit_identifier") in _DEBIT_CREDIT_IDENTIFIER_VALUES
    assert isinstance(record.get("is_cleared"), bool)
    assert isinstance(record.get("open_balance_of_item"), (int, float))


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-payable ---


def test_accounts_payable_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ACCOUNTS_PAYABLE, (
        f"expected at least {MIN_ACCOUNTS_PAYABLE} accounts-payable records, got {len(records)}"
    )


def test_accounts_payable_record_has_core_fields(client):
    records = _get(client, ACCOUNTS_PAYABLE_ENDPOINT)
    assert records, "no accounts-payable records returned"

    for record in records:
        _assert_open_item_core_fields(record)


def test_accounts_payable_ignores_path_param_values(client):
    first = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-payable/condense ---


def test_accounts_payable_condense_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ACCOUNTS_PAYABLE_CONDENSE, (
        f"expected at least {MIN_ACCOUNTS_PAYABLE_CONDENSE} condensed accounts-payable records, "
        f"got {len(records)}"
    )


def test_accounts_payable_condense_record_has_core_fields(client):
    """Same schema as plain accounts-payable (server-side aggregation, not a
    different shape), so it's held to the same core-fields contract."""
    records = _get(client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT)
    assert records, "no condensed accounts-payable records returned"

    for record in records:
        _assert_open_item_core_fields(record)


def test_accounts_payable_condense_ignores_path_param_values(client):
    first = _get(
        client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    second = _get(
        client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-receivable/condense ---


def test_accounts_receivable_condense_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ACCOUNTS_RECEIVABLE_CONDENSE, (
        f"expected at least {MIN_ACCOUNTS_RECEIVABLE_CONDENSE} condensed accounts-receivable "
        f"records, got {len(records)}"
    )


def test_accounts_receivable_condense_record_has_core_fields(client):
    """Shares accounts-payable's core fields, plus receivable-only
    `dunning_level` — a RED-imposed fake-data contract requiring it
    populated on every record (the OpenAPI schema itself doesn't mark it
    required), mirroring Phase A's precedent for addressee type-specific
    fields."""
    records = _get(client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT)
    assert records, "no condensed accounts-receivable records returned"

    for record in records:
        _assert_open_item_core_fields(record)
        assert isinstance(record.get("dunning_level"), str) and record["dunning_level"].strip()


def test_accounts_receivable_condense_ignores_path_param_values(client):
    first = _get(
        client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    second = _get(
        client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    assert first == second


# --- payable vs. condensed payable independence ---


def test_payable_and_condense_endpoints_both_work_for_the_same_ids(client):
    """Both endpoints must work independently for the same client/fiscal-year
    ids — deliberately not asserting their bodies are identical, since
    condense is documented as a real server-side aggregation in the real
    API."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()

    plain_response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id)
    )
    condensed_response = client.get(
        ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id)
    )

    assert plain_response.status_code == 200
    assert condensed_response.status_code == 200
    assert isinstance(plain_response.json(), list) and plain_response.json()
    assert isinstance(condensed_response.json(), list) and condensed_response.json()
