"""Tests for the Accounting open-item endpoints (epic
`datev-mock-extended-endpoints`, Phase B, batch B2; expanded in epic
`datev-mock-real-data-reconciliation`, W3).

Covers 3 of the 15 target endpoints:
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-payable` (compiled spec
    doc #6)
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-payable/condense`
    (compiled spec doc #2 — **same schema** as accounts-payable, condense is
    server-side aggregation, not a different shape)
  - `GET .../fiscal-years/{fiscal-year-id}/accounts-receivable/condense`
    (compiled spec doc #3)

Field shape ground truth (W3): direct occurrence counts against
`examples/condense.xml` (accounts-payable/condense, 3642 real records) and
`examples/accounts-receivable-condense.xml` (3455 real records) — never
real values, only field-name presence counts. See `app/models.py`'s
`OpenItem` docstring for the full evidence and the **correction** this
batch made to the epic doc's original "payable vs. receivable have
different optional fields" framing: direct counts show payable and
receivable share the *same* optional-field set at matching presence rates
(the epic doc's table was apparently derived from a single first-record
sample, not a full count). Originally this suite also asserted an invented
`dunning_level` field; corrected in W1 — real evidence showed no such field
exists, replaced by `has_dunning_block`.

- JSON-only bare arrays by default is no longer accurate as of W3: all 3
  endpoints now support XML/JSON content negotiation (inferred by pattern,
  same mechanism as `accounting.clients` — see the XML tests below).
  Bare/ambiguous Accept now defaults to XML, so every JSON assertion below
  passes an explicit `Accept: application/json` header.
- `{client-id}` / `{fiscal-year-id}` path params never filter the dataset —
  tested explicitly below, not just documented.
- `accounts-payable/condense` and `accounts-payable` share the same schema;
  this suite tests both work independently, without asserting their bodies
  are identical (condense is a real server-side aggregation in the real
  API, even though this mock doesn't implement aggregation logic).
"""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET

from app.routers.accounting import (
    ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT,
    ACCOUNTS_PAYABLE_ENDPOINT,
    ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT,
    COST_CENTERS_ENDPOINT,
    COST_SYSTEMS_ENDPOINT,
    TERMS_OF_PAYMENT_ENDPOINT,
)
from app.xml_serializers import OPEN_ITEM_NS

MIN_ACCOUNTS_PAYABLE = 3
MIN_ACCOUNTS_PAYABLE_CONDENSE = 3
MIN_ACCOUNTS_RECEIVABLE_CONDENSE = 3

JSON_ACCEPT_HEADERS = {"accept": "application/json"}
XML_ACCEPT_HEADERS = {"accept": "application/xml"}
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NIL_ATTR = f"{{{XSI_NS}}}nil"

_EVIDENCE_TYPE_VALUES = {
    "invoice",
    "credit_note",
    "credit_note_by_revocation",
    "deposit",
    "payment",
    "cash_discount",
}
_DEBIT_CREDIT_IDENTIFIER_VALUES = {"S", "H"}


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _xml_field(record: ET.Element, local_name: str) -> ET.Element:
    for child in record:
        if _local_name(child.tag) == local_name:
            return child
    raise AssertionError(f"expected field {local_name!r} not found")


def _is_nil(field_el: ET.Element) -> bool:
    return field_el.get(NIL_ATTR) == "true"


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get(client, endpoint_template: str, client_id: str | None = None, fiscal_year_id: str | None = None) -> list[dict]:
    response = client.get(
        endpoint_template.format(
            client_id=client_id or _fresh_id(), fiscal_year_id=fiscal_year_id or _fresh_id()
        ),
        headers=JSON_ACCEPT_HEADERS,
    )
    return response.json()


def _assert_open_item_core_fields(record: dict) -> None:
    """Real, always-present fields (100% on both real capture files — see
    `OpenItem`'s docstring in `app/models.py`)."""
    assert isinstance(record.get("id"), str) and record["id"].strip()
    assert isinstance(record.get("account_number"), int)
    assert isinstance(record.get("accounting_sequence_id"), str) and record["accounting_sequence_id"].strip()
    assert isinstance(record.get("date"), str) and record["date"].strip()
    assert record.get("debit_credit_identifier") in _DEBIT_CREDIT_IDENTIFIER_VALUES
    assert isinstance(record.get("document_field1"), str) and record["document_field1"].strip()
    assert record.get("evidence_type") in _EVIDENCE_TYPE_VALUES
    assert isinstance(record.get("has_interest_block"), bool)
    assert isinstance(record.get("is_cleared"), bool)
    assert isinstance(record.get("is_condensed"), bool)
    assert isinstance(record.get("open_balance_of_item"), (int, float))
    assert isinstance(record.get("open_item_number"), str) and record["open_item_number"].strip()
    assert isinstance(record.get("payment_method"), str) and record["payment_method"].strip()
    assert isinstance(record.get("posting_description"), str) and record["posting_description"].strip()
    assert isinstance(record.get("posting_record_number"), int)
    assert isinstance(record.get("tax_rate"), (int, float))
    # pre-existing, unconfirmed fields — kept, not part of the real shape
    assert isinstance(record.get("amount_entered"), (int, float))
    assert isinstance(record.get("currency_code"), str) and record["currency_code"].strip()
    # amount_debit/amount_credit are mutually exclusive per record (driven
    # by debit_credit_identifier) — exactly one is present, never both.
    has_debit = record.get("amount_debit") is not None
    has_credit = record.get("amount_credit") is not None
    assert has_debit != has_credit, (
        "expected exactly one of amount_debit/amount_credit to be present"
    )
    if has_debit:
        assert isinstance(record["amount_debit"], (int, float))
    else:
        assert isinstance(record["amount_credit"], (int, float))


def _assert_open_item_xml_root_and_namespace(response, expected_min: int) -> ET.Element:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{OPEN_ITEM_NS}}}ArrayOfOpenItem"

    records = [child for child in root if _local_name(child.tag) == "OpenItem"]
    assert len(records) >= expected_min
    return root


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-payable ---


def test_accounts_payable_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
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


def test_accounts_payable_same_ids_are_stable(client):
    """P3 (odd/tasks/datev-mock-referential-integrity.md, decision #7):
    replaces the old *_ignores_path_param_values test, which asserted the
    literal opposite of the current design. Same (client_id, fiscal_year_id)
    used twice must return identical data."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    first = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id)
    second = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id)
    assert first == second


def test_accounts_payable_different_ids_return_different_data(client):
    first = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    for _ in range(3):
        candidate = _get(
            client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
        )
        if candidate != first:
            return
    raise AssertionError("expected accounts-payable to differ across fresh scope ids")


def test_accounts_payable_term_of_payment_id_resolves_to_scope_terms_of_payment(client):
    """New cross-reference coverage (decision #7): architecture decision #4
    draws OpenItem.term_of_payment_id from this same (client_id,
    fiscal_year_id) scope's own generated TermOfPayment.id list, not
    reinvented arithmetic -- proven here by cross-checking against the
    terms-of-payment endpoint for the same scope."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    records = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id)
    records_with_term = [r for r in records if r.get("term_of_payment_id") is not None]
    assert records_with_term, "no accounts-payable record carries term_of_payment_id"

    terms = client.get(
        TERMS_OF_PAYMENT_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id),
        headers=JSON_ACCEPT_HEADERS,
    ).json()
    term_ids = {int(term["id"]) for term in terms}
    for record in records_with_term:
        assert record["term_of_payment_id"] in term_ids


def test_accounts_payable_kost1_cost_center_id_resolves_to_primary_cost_system_cost_centers(client):
    """New cross-reference coverage (decision #7): architecture decision #4
    references the fiscal year's *primary* cost system (index 0) for
    OpenItem.kost1_cost_center_id -- proven here by cross-checking against
    that specific cost system's cost-centers endpoint."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    records = _get(client, ACCOUNTS_PAYABLE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id)
    records_with_cost_center = [r for r in records if r.get("kost1_cost_center_id") is not None]
    assert records_with_cost_center, "no accounts-payable record carries kost1_cost_center_id"

    cost_systems = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id),
        headers=JSON_ACCEPT_HEADERS,
    ).json()
    primary_cost_system_id = cost_systems[0]["id"]
    cost_centers = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=client_id, fiscal_year_id=fiscal_year_id, cost_system_id=primary_cost_system_id
        ),
        headers=JSON_ACCEPT_HEADERS,
    ).json()
    cost_center_ids = {c["id"] for c in cost_centers}
    for record in records_with_cost_center:
        assert record["kost1_cost_center_id"] in cost_center_ids


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-payable/condense ---


def test_accounts_payable_condense_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
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


def test_accounts_payable_condense_same_ids_are_stable(client):
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    first = _get(
        client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id
    )
    second = _get(
        client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id
    )
    assert first == second


def test_accounts_payable_condense_different_ids_return_different_data(client):
    first = _get(
        client, ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    for _ in range(3):
        candidate = _get(
            client,
            ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT,
            client_id=_fresh_id(),
            fiscal_year_id=_fresh_id(),
        )
        if candidate != first:
            return
    raise AssertionError("expected condensed accounts-payable to differ across fresh scope ids")


# --- GET .../fiscal-years/{fiscal-year-id}/accounts-receivable/condense ---


def test_accounts_receivable_condense_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
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
    """Corrected per real evidence (epic `datev-mock-real-data-reconciliation`,
    W1): this test previously asserted this project's own invented
    `dunning_level` field (a RED-imposed fake-data contract, not
    spec-derived). Real captured evidence
    (`examples/accounts-receivable-condense.xml`, JSON content) shows
    `dunning_level` does not exist — the real, analogous field is
    `has_dunning_block` (boolean), present on every record."""
    records = _get(client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT)
    assert records, "no condensed accounts-receivable records returned"

    for record in records:
        _assert_open_item_core_fields(record)
        assert isinstance(record.get("has_dunning_block"), bool)


def test_accounts_receivable_condense_same_ids_are_stable(client):
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    first = _get(
        client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id
    )
    second = _get(
        client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT, client_id=client_id, fiscal_year_id=fiscal_year_id
    )
    assert first == second


def test_accounts_receivable_condense_different_ids_return_different_data(client):
    first = _get(
        client, ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id()
    )
    for _ in range(3):
        candidate = _get(
            client,
            ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT,
            client_id=_fresh_id(),
            fiscal_year_id=_fresh_id(),
        )
        if candidate != first:
            return
    raise AssertionError("expected condensed accounts-receivable to differ across fresh scope ids")


# --- payable vs. condensed payable independence ---


def test_payable_and_condense_endpoints_both_work_for_the_same_ids(client):
    """Both endpoints must work independently for the same client/fiscal-year
    ids — deliberately not asserting their bodies are identical, since
    condense is documented as a real server-side aggregation in the real
    API."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()

    plain_response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id),
        headers=JSON_ACCEPT_HEADERS,
    )
    condensed_response = client.get(
        ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id),
        headers=JSON_ACCEPT_HEADERS,
    )

    assert plain_response.status_code == 200
    assert condensed_response.status_code == 200
    assert isinstance(plain_response.json(), list) and plain_response.json()
    assert isinstance(condensed_response.json(), list) and condensed_response.json()


# --- XML content negotiation (W3, epic `datev-mock-real-data-reconciliation`) ---
#
# Inferred by pattern — no direct real XML evidence for any of the 3
# open-item endpoints (both real captures were JSON content despite their
# `.xml` filenames). All 3 share the same `OpenItem` shape/root tag.


def test_accounts_payable_xml_root_tag_and_namespace(client):
    response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    _assert_open_item_xml_root_and_namespace(response, MIN_ACCOUNTS_PAYABLE)


def test_accounts_payable_condense_xml_root_tag_and_namespace(client):
    response = client.get(
        ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    _assert_open_item_xml_root_and_namespace(response, MIN_ACCOUNTS_PAYABLE_CONDENSE)


def test_accounts_receivable_condense_xml_root_tag_and_namespace(client):
    response = client.get(
        ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    _assert_open_item_xml_root_and_namespace(response, MIN_ACCOUNTS_RECEIVABLE_CONDENSE)


def test_accounts_payable_xml_optional_field_uses_nil_when_absent(client):
    """`balancing_type`/`contra_account_number`/`kost1_cost_center_id` are
    genuinely optional in this mock's fake data (matching the real ~88-99%
    presence rate, absent on the last generated record) — exercised via
    `contra_account_number`."""
    response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    root = ET.fromstring(response.content)
    records = [child for child in root if _local_name(child.tag) == "OpenItem"]

    nil_seen = any(_is_nil(_xml_field(record, "ContraAccountNumber")) for record in records)
    assert nil_seen, (
        "expected at least one OpenItem record with ContraAccountNumber i:nil='true'"
    )


def test_accounts_payable_default_format_is_xml(client):
    """Ambiguous/missing Accept defaults to the live `default_accounting_format`
    setting (`"xml"`), same as every other content-negotiated endpoint."""
    response = client.get(
        ACCOUNTS_PAYABLE_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
