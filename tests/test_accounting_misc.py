"""RED-phase tests for the remaining Accounting sub-resource endpoints (epic
`datev-mock-extended-endpoints`, Phase B, batch B2).

Covers 7 of the 15 target endpoints:
  - `GET .../fiscal-years/{fiscal-year-id}/accounting-sequences-processed`
    (compiled spec doc #4)
  - `GET .../fiscal-years/{fiscal-year-id}/accounting-transaction-keys`
    (compiled spec doc #5)
  - `GET .../fiscal-years/{fiscal-year-id}/assets/stocktakings`
    (compiled spec doc #7)
  - `GET .../fiscal-years/{fiscal-year-id}/general-ledger-accounts`
    (compiled spec doc #12)
  - `GET .../fiscal-years/{fiscal-year-id}/posting-proposal-rules-incoming-invoices`
    (compiled spec doc #13)
  - `GET .../fiscal-years/{fiscal-year-id}/posting-proposal-rules-outgoing-invoices`
    (compiled spec doc #14)
  - `GET .../fiscal-years/{fiscal-year-id}/terms-of-payment` (compiled spec
    doc #15)

Ground truth: the compiled OpenAPI reference written to the session
scratchpad's `datev-endpoint-specs.md`, plus the cross-phase decisions in
`odd/tasks/datev-mock-extended-endpoints.md`:

- JSON-only bare arrays, no pagination wrapper.
- `{client-id}` / `{fiscal-year-id}` path params never filter the dataset —
  tested explicitly below for every endpoint, not just documented.
- `general-ledger-account.main_function` / `main_function_number` /
  `additional_function` are typed as plain `integer` in the spec, with valid
  values only documented in free-text description (no OpenAPI `enum`) — the
  epic doc flags these as needing a hardcoded lookup table; this suite
  asserts values fall within the documented value sets rather than an
  open-ended integer range.
- `term-of-payment.due_type` gates which of `due_in_days`/`due_as_period` is
  populated — tested as a parallel-fields contract, same pattern as Phase A's
  `Addressee.type` and this batch's `creditor`/`debitor.legal_entity_type`.

These tests intentionally import the `*_ENDPOINT` constants directly from
`app.routers.accounting`, which do not exist yet. This import is expected to
fail at collection time (`ImportError`) until the GREEN-phase router work
(tasks B1/B2-GREEN) adds these endpoints and their constants — that failure
is the correct RED signal for this task; do not add a try/except around it
to hide it.
"""
from __future__ import annotations

import uuid

from app.routers.accounting import (
    ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT,
    ACCOUNTING_TRANSACTION_KEYS_ENDPOINT,
    ASSETS_STOCKTAKINGS_ENDPOINT,
    GENERAL_LEDGER_ACCOUNTS_ENDPOINT,
    POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT,
    POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT,
    TERMS_OF_PAYMENT_ENDPOINT,
)

MIN_ACCOUNTING_SEQUENCES_PROCESSED = 3
MIN_ACCOUNTING_TRANSACTION_KEYS = 3
MIN_ASSETS_STOCKTAKINGS = 3
MIN_GENERAL_LEDGER_ACCOUNTS = 5
MIN_POSTING_PROPOSAL_RULES_INCOMING_INVOICES = 3
MIN_POSTING_PROPOSAL_RULES_OUTGOING_INVOICES = 3
MIN_TERMS_OF_PAYMENT = 3

_RECORD_TYPE_VALUES = {"financial_accounting", "annual_financial_statements"}
_ACCOUNTING_REASON_VALUES = {
    "independent_from_accounting_reason",
    "reserved1",
    "reserved2",
    "commercial_law",
    "tax_law",
    "ifrs",
    "for_calculation",
}
_STOCKTAKING_ACCOUNTING_REASON_VALUES = {50, 30, 40, 64, 11, 12}
# `0` added per real evidence (epic `datev-mock-real-data-reconciliation`,
# W1, `examples/general-ledger-accounts.xml`) — a real observed value for
# both fields, not covered by the original 1-based ranges.
_MAIN_FUNCTION_VALUES = {0, 1, 2, 3, 4, 5, 6, 7}
_MAIN_FUNCTION_NUMBER_VALUES = {0, 10, 11, 12, 20, 21, 25, 90, 91, 98}
_ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES = {
    "own_input",
    "posting_description",
    "goods_and_services",
    "business_partner_name",
    "not_specified",
}
_ORIGIN_OF_POSTING_DESCRIPTION_OUTGOING_VALUES = _ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES | {
    "email",
    "transaction_key",
}
_DUE_TYPE_VALUES = {"due_in_days", "due_as_period"}
_RELATED_MONTH_VALUES = {"current_month", "next_month", "month_after_next"}


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get(client, endpoint_template: str, client_id: str | None = None, fiscal_year_id: str | None = None) -> list[dict]:
    response = client.get(
        endpoint_template.format(
            client_id=client_id or _fresh_id(), fiscal_year_id=fiscal_year_id or _fresh_id()
        )
    )
    return response.json()


def _assert_ignores_path_params(client, endpoint_template: str) -> None:
    first = _get(client, endpoint_template, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get(client, endpoint_template, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/accounting-sequences-processed ---


def test_accounting_sequences_processed_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ACCOUNTING_SEQUENCES_PROCESSED, (
        f"expected at least {MIN_ACCOUNTING_SEQUENCES_PROCESSED} accounting-sequence records, "
        f"got {len(records)}"
    )


def test_accounting_sequence_record_has_core_fields(client):
    records = _get(client, ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT)
    assert records, "no accounting-sequence records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("accounting_sequence_id"), str) and record["accounting_sequence_id"].strip()
        assert isinstance(record.get("description"), str) and record["description"].strip()
        assert isinstance(record.get("date_from"), str) and record["date_from"].strip()
        assert isinstance(record.get("date_to"), str) and record["date_to"].strip()
        assert isinstance(record.get("is_committed"), bool)
        assert record.get("record_type") in _RECORD_TYPE_VALUES
        assert record.get("accounting_reason") in _ACCOUNTING_REASON_VALUES


def test_accounting_sequences_processed_ignores_path_param_values(client):
    _assert_ignores_path_params(client, ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/accounting-transaction-keys ---


def test_accounting_transaction_keys_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTING_TRANSACTION_KEYS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ACCOUNTING_TRANSACTION_KEYS, (
        f"expected at least {MIN_ACCOUNTING_TRANSACTION_KEYS} accounting-transaction-key records, "
        f"got {len(records)}"
    )


def test_accounting_transaction_key_record_has_core_fields(client):
    records = _get(client, ACCOUNTING_TRANSACTION_KEYS_ENDPOINT)
    assert records, "no accounting-transaction-key records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("caption"), str)
        assert isinstance(record.get("number"), int) and 1 <= record["number"] <= 9999
        assert isinstance(record.get("tax_rate"), (int, float)) and 0 <= record["tax_rate"] <= 99.99
        assert isinstance(record.get("is_tax_rate_selectable"), bool)


def test_accounting_transaction_keys_ignores_path_param_values(client):
    _assert_ignores_path_params(client, ACCOUNTING_TRANSACTION_KEYS_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/assets/stocktakings ---


def test_assets_stocktakings_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ASSETS_STOCKTAKINGS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_ASSETS_STOCKTAKINGS, (
        f"expected at least {MIN_ASSETS_STOCKTAKINGS} stocktaking records, got {len(records)}"
    )


def test_stocktaking_record_has_required_core_fields(client):
    """`asset_number` and `inventory_number` are the only two fields the spec
    itself marks `required` for this schema."""
    records = _get(client, ASSETS_STOCKTAKINGS_ENDPOINT)
    assert records, "no stocktaking records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("asset_number"), int)
        assert isinstance(record.get("inventory_number"), str) and record["inventory_number"].strip()
        assert record.get("accounting_reason") in _STOCKTAKING_ACCOUNTING_REASON_VALUES


def test_stocktaking_general_ledger_account_is_nested_object(client):
    records = _get(client, ASSETS_STOCKTAKINGS_ENDPOINT)
    records_with_account = [r for r in records if r.get("general_ledger_account")]
    assert records_with_account, "no stocktaking record carries a populated general_ledger_account"

    for record in records_with_account:
        account = record["general_ledger_account"]
        assert isinstance(account.get("account_number"), int)
        assert isinstance(account.get("caption"), str) and account["caption"].strip()


def test_assets_stocktakings_ignores_path_param_values(client):
    _assert_ignores_path_params(client, ASSETS_STOCKTAKINGS_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/general-ledger-accounts ---


def test_general_ledger_accounts_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        GENERAL_LEDGER_ACCOUNTS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_GENERAL_LEDGER_ACCOUNTS, (
        f"expected at least {MIN_GENERAL_LEDGER_ACCOUNTS} general-ledger-account records, "
        f"got {len(records)}"
    )


def test_general_ledger_account_record_has_core_fields(client):
    records = _get(client, GENERAL_LEDGER_ACCOUNTS_ENDPOINT)
    assert records, "no general-ledger-account records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("account_number"), int)
        assert isinstance(record.get("caption"), str) and record["caption"].strip()


def test_general_ledger_account_main_function_values_use_hardcoded_lookup_range(client):
    """`main_function`/`main_function_number` are typed as plain `integer` in
    the spec with valid values documented only in free-text description, not
    an OpenAPI `enum` — the epic doc explicitly flags these as needing a
    hardcoded lookup, so this test pins the fake data to those documented
    value sets instead of an unconstrained integer."""
    records = _get(client, GENERAL_LEDGER_ACCOUNTS_ENDPOINT)
    assert records, "no general-ledger-account records returned"

    for record in records:
        assert record.get("main_function") in _MAIN_FUNCTION_VALUES
        assert record.get("main_function_number") in _MAIN_FUNCTION_NUMBER_VALUES


def test_general_ledger_accounts_ignores_path_param_values(client):
    _assert_ignores_path_params(client, GENERAL_LEDGER_ACCOUNTS_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/posting-proposal-rules-incoming-invoices ---


def test_posting_proposal_rules_incoming_invoices_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id()
        )
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_POSTING_PROPOSAL_RULES_INCOMING_INVOICES, (
        f"expected at least {MIN_POSTING_PROPOSAL_RULES_INCOMING_INVOICES} "
        f"posting-proposal-rule (incoming) records, got {len(records)}"
    )


def test_posting_proposal_rule_incoming_record_has_core_fields(client):
    records = _get(client, POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT)
    assert records, "no posting-proposal-rule (incoming) records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("uncertain_label"), bool)

        criteria = record.get("assignment_criteria")
        assert isinstance(criteria, dict)
        assert isinstance(criteria.get("name"), str) and criteria["name"].strip()
        assert isinstance(criteria.get("tax_rate"), (int, float))

        proposal_info = record.get("posting_proposal_information")
        assert isinstance(proposal_info, list) and proposal_info
        for entry in proposal_info:
            assert isinstance(entry.get("accounting_transaction_key"), int)
            assert 1 <= entry["accounting_transaction_key"] <= 9999
            assert isinstance(entry.get("account_number"), int)
            assert entry.get("origin_of_posting_description") in (
                _ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES
            )


def test_posting_proposal_rules_incoming_invoices_ignores_path_param_values(client):
    _assert_ignores_path_params(client, POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/posting-proposal-rules-outgoing-invoices ---


def test_posting_proposal_rules_outgoing_invoices_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id()
        )
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_POSTING_PROPOSAL_RULES_OUTGOING_INVOICES, (
        f"expected at least {MIN_POSTING_PROPOSAL_RULES_OUTGOING_INVOICES} "
        f"posting-proposal-rule (outgoing) records, got {len(records)}"
    )


def test_posting_proposal_rule_outgoing_record_has_core_fields(client):
    """Identical shape to the incoming variant except
    `origin_of_posting_description` carries two extra enum values
    (`email`, `transaction_key`) — tested via the wider allowed-value set."""
    records = _get(client, POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT)
    assert records, "no posting-proposal-rule (outgoing) records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("uncertain_label"), bool)

        criteria = record.get("assignment_criteria")
        assert isinstance(criteria, dict)
        assert isinstance(criteria.get("name"), str) and criteria["name"].strip()

        proposal_info = record.get("posting_proposal_information")
        assert isinstance(proposal_info, list) and proposal_info
        for entry in proposal_info:
            assert entry.get("origin_of_posting_description") in (
                _ORIGIN_OF_POSTING_DESCRIPTION_OUTGOING_VALUES
            )


def test_posting_proposal_rules_outgoing_invoices_ignores_path_param_values(client):
    _assert_ignores_path_params(client, POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT)


# --- GET .../fiscal-years/{fiscal-year-id}/terms-of-payment ---


def test_terms_of_payment_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        TERMS_OF_PAYMENT_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_TERMS_OF_PAYMENT, (
        f"expected at least {MIN_TERMS_OF_PAYMENT} term-of-payment records, got {len(records)}"
    )


def test_term_of_payment_record_has_required_caption(client):
    """`caption` is the only field the spec itself marks `required`."""
    records = _get(client, TERMS_OF_PAYMENT_ENDPOINT)
    assert records, "no term-of-payment records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("caption"), str) and record["caption"].strip()
        assert record.get("due_type") in _DUE_TYPE_VALUES


def test_term_of_payment_due_type_matches_populated_variant(client):
    """`due_type` gates which of `due_in_days`/`due_as_period` is populated —
    the same parallel-fields convention already tested for `Addressee.type`
    (Phase A) and `legal_entity_type` (this batch's creditors/debitors).
    Requires the fake dataset to contain at least one record of each
    variant, not just declare the enum."""
    records = _get(client, TERMS_OF_PAYMENT_ENDPOINT)

    due_in_days_records = [r for r in records if r.get("due_type") == "due_in_days"]
    due_as_period_records = [r for r in records if r.get("due_type") == "due_as_period"]
    assert due_in_days_records, "no due_in_days term-of-payment records returned"
    assert due_as_period_records, "no due_as_period term-of-payment records returned"

    for record in due_in_days_records:
        due_in_days = record.get("due_in_days")
        assert isinstance(due_in_days, dict)
        assert isinstance(due_in_days.get("due_in_days"), int)

    for record in due_as_period_records:
        due_as_period = record.get("due_as_period")
        assert isinstance(due_as_period, dict)
        period1 = due_as_period.get("period1")
        assert isinstance(period1, dict)
        assert isinstance(period1.get("invoice_day_of_month"), int)
        due_date_net = period1.get("due_date_net")
        assert isinstance(due_date_net, dict)
        assert due_date_net.get("related_month") in _RELATED_MONTH_VALUES
        assert isinstance(due_date_net.get("day_of_month"), int)


def test_terms_of_payment_ignores_path_param_values(client):
    _assert_ignores_path_params(client, TERMS_OF_PAYMENT_ENDPOINT)
