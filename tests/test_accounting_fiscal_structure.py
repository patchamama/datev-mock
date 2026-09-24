"""RED-phase tests for the Accounting fiscal-year/cost-system structure
endpoints (epic `datev-mock-extended-endpoints`, Phase B, batch B1).

Covers 3 of the 15 target endpoints:
  - `GET /clients/{client-id}/fiscal-years` (compiled spec doc #1, client-level,
    not fiscal-year-scoped)
  - `GET .../fiscal-years/{fiscal-year-id}/cost-systems` (compiled spec doc #8)
  - `GET .../fiscal-years/{fiscal-year-id}/cost-systems/{cost-system-id}/cost-centers`
    (compiled spec doc #9)

Ground truth: the compiled OpenAPI reference written to the session
scratchpad's `datev-endpoint-specs.md`, plus the cross-phase decisions in
`odd/tasks/datev-mock-extended-endpoints.md`:

- All accounting list endpoints are JSON-only bare arrays (never a pagination
  wrapper).
- `{client-id}` / `{fiscal-year-id}` / `{cost-system-id}` path params are
  accepted but never filter the returned dataset — every call returns the
  same generic fake fixture regardless of the specific ids in the URL. This
  is explicitly tested below (`*_ignores_*_id_values`), not just documented.
- `cost-center.cost_rates[].valid_from`/`valid_to` are integer-encoded dates
  (e.g. `20161201`), not date-time strings — a spec quirk called out
  explicitly in the epic doc, tested below.

These tests intentionally import `FISCAL_YEARS_ENDPOINT` / `COST_SYSTEMS_ENDPOINT`
/ `COST_CENTERS_ENDPOINT` directly from `app.routers.accounting`, which do not
exist yet (only the existing XML `clients` endpoint's `ENDPOINT` constant is
defined there). This import is expected to fail at collection time
(`ImportError`) until the GREEN-phase router work (tasks B1/B2-GREEN) adds
these endpoints and their constants — that failure is the correct RED signal
for this task; do not add a try/except around it to hide it.
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET

from app.routers.accounting import (
    COST_CENTERS_ENDPOINT,
    COST_SYSTEMS_ENDPOINT,
    FISCAL_YEARS_ENDPOINT,
    TERMS_OF_PAYMENT_ENDPOINT,
)

MIN_FISCAL_YEARS = 2
MIN_COST_SYSTEMS = 2
MIN_COST_CENTERS = 3

# Content negotiation (epic `datev-mock-real-data-reconciliation`, W2): these
# 3 endpoints now default to XML (same mechanism as accounting.clients) when
# the Accept header doesn't explicitly request JSON — every bare-JSON
# assertion below must pass this header explicitly.
JSON_ACCEPT_HEADERS = {"accept": "application/json"}
XML_ACCEPT_HEADERS = {"accept": "application/xml"}

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NIL_ATTR = f"{{{XSI_NS}}}nil"
FISCAL_YEAR_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.FiscalYear"
)
COST_SYSTEMS_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.CostSystems"
)
COST_CENTER_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.CostCenter"
)


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _field(record: ET.Element, local_name: str) -> ET.Element:
    for child in record:
        if _local_name(child.tag) == local_name:
            return child
    raise AssertionError(f"expected field {local_name!r} not found")


def _is_nil(field_el: ET.Element) -> bool:
    return field_el.get(NIL_ATTR) == "true"

_LEGAL_FORM_VALUES = {
    "not_specified",
    "sole_proprietorship",
    "corporation",
    "cooperative",
    "partnership_under_the_german_civil_code",
    "limited_partnership_with_a_limited_liability_company_as_general_partner",
    "limited_partnership",
    "general_partnership",
    "association",
    "foundation",
    "public_corporation",
    "corporation_under_communal_budget_ordinance",
    "non_profit_corporation",
}
_TAXATION_METHOD_VALUES = {
    "not_specified",
    "taxation_based_on_value_of_services_rendered",
    "taxation_based_on_value_of_actual_receipts",
    "taxation_based_on_value_of_actual_receipts_input_tax_deduction_at_payment",
    "no_vat_calculation",
    "lump_sum",
}
_NATIONAL_RIGHT_VALUES = {"DE", "AT"}

_YYYYMMDD_RE = re.compile(r"^\d{8}$")


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get_fiscal_years(client, client_id: str = "any-client") -> list[dict]:
    response = client.get(
        FISCAL_YEARS_ENDPOINT.format(client_id=client_id), headers=JSON_ACCEPT_HEADERS
    )
    return response.json()


def _get_cost_systems(client, client_id: str = "any-client", fiscal_year_id: str = "any-fy") -> list[dict]:
    response = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id),
        headers=JSON_ACCEPT_HEADERS,
    )
    return response.json()


def _get_cost_centers(
    client,
    client_id: str = "any-client",
    fiscal_year_id: str = "any-fy",
    cost_system_id: str = "any-cs",
) -> list[dict]:
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=client_id, fiscal_year_id=fiscal_year_id, cost_system_id=cost_system_id
        ),
        headers=JSON_ACCEPT_HEADERS,
    )
    return response.json()


# --- GET .../clients/{client-id}/fiscal-years ---


def test_fiscal_years_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        FISCAL_YEARS_ENDPOINT.format(client_id=_fresh_id()), headers=JSON_ACCEPT_HEADERS
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_FISCAL_YEARS, (
        f"expected at least {MIN_FISCAL_YEARS} fiscal-year records, got {len(records)}"
    )


def test_fiscal_year_record_has_core_fields(client):
    records = _get_fiscal_years(client)
    assert records, "no fiscal-year records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and _YYYYMMDD_RE.match(record["id"]), (
            "fiscal-year id must be a YYYYMMDD-formatted string"
        )
        assert isinstance(record.get("account_system"), int)
        assert isinstance(record.get("currency_code"), str) and 1 <= len(record["currency_code"]) <= 3
        # `legal_form` is genuinely optional (real evidence:
        # `examples/fiscal-years.xml` — absent, not null, on some records) —
        # corrected from the earlier "always populated, always a member of
        # the enum" assumption.
        if "legal_form" in record:
            assert record["legal_form"] in _LEGAL_FORM_VALUES
        assert record.get("taxation_method") in _TAXATION_METHOD_VALUES
        assert record.get("national_right") in _NATIONAL_RIGHT_VALUES
        assert isinstance(record.get("is_locked"), bool)


def test_fiscal_year_record_has_expanded_real_fields(client):
    """Real evidence (`examples/fiscal-years.xml`, epic
    `datev-mock-real-data-reconciliation`, W2): the real shape is 23
    top-level fields, 19 always present. Asserts the always-present ones not
    already covered by `test_fiscal_year_record_has_core_fields`."""
    records = _get_fiscal_years(client)
    assert records, "no fiscal-year records returned"

    for record in records:
        assert isinstance(record.get("account_length"), int)
        assert isinstance(record.get("advance_turnover_tax_return"), str) and record[
            "advance_turnover_tax_return"
        ].strip()
        assert isinstance(record.get("begin"), str) and record["begin"].strip()
        assert isinstance(record.get("end"), str) and record["end"].strip()
        assert isinstance(record.get("client_number"), int)
        assert isinstance(record.get("consultant_number"), int)
        assert isinstance(record.get("cost_length"), int)
        assert isinstance(record.get("creditor_term_of_payment_id"), int)
        assert isinstance(record.get("is_invoice_date_check_on"), bool)
        assert isinstance(record.get("is_using_delivery_date"), bool)
        assert isinstance(record.get("is_using_individual_referencesystem"), bool)
        assert isinstance(record.get("is_using_receivable_type"), bool)
        assert isinstance(record.get("is_using_referencesystem"), bool)


def test_fiscal_year_optional_fields_are_genuinely_absent_on_some_records(client):
    """Locks in the real sparsity pattern (not just "the field type is
    Optional") — at least one record must lack each of the 4 genuinely
    optional fields, and at least one must carry it, for every one of them."""
    records = _get_fiscal_years(client)
    assert records, "no fiscal-year records returned"

    for optional_field in (
        "basis_of_checking_account_function",
        "debitor_term_of_payment_id",
        "legal_form",
        "method_of_determining_net_income",
    ):
        present = [r for r in records if optional_field in r]
        absent = [r for r in records if optional_field not in r]
        assert present, f"expected at least one record with {optional_field!r} present"
        assert absent, f"expected at least one record with {optional_field!r} absent"


def test_fiscal_years_same_client_id_is_stable(client):
    """P3 (odd/tasks/datev-mock-referential-integrity.md, decision #7):
    replaces the old *_ignores_client_id_value test, which asserted the
    literal opposite of the current design. Same client_id used twice must
    return identical data -- proves per-scope caching/determinism
    (architecture decisions #1/#3)."""
    client_id = _fresh_id()
    first = _get_fiscal_years(client, client_id=client_id)
    second = _get_fiscal_years(client, client_id=client_id)
    assert first == second


def test_fiscal_years_different_client_id_returns_different_data(client):
    """Two different client ids must return different data -- proves real
    per-scope generation, not the old "always the same fixed dataset"
    behavior. Retries a few fresh ids before failing: a couple of the
    varying fields (e.g. base_year) are drawn from a small value set, so two
    independently-random scopes could rarely coincide by chance on the
    first draw alone."""
    first = _get_fiscal_years(client, client_id=_fresh_id())
    for _ in range(5):
        candidate = _get_fiscal_years(client, client_id=_fresh_id())
        if candidate != first:
            return
    raise AssertionError("expected fiscal years to differ across fresh client ids")


def test_fiscal_year_creditor_term_of_payment_id_resolves_to_scope_terms_of_payment(client):
    """New cross-reference coverage (decision #7): architecture decision #4
    backfills FiscalYear.creditor_term_of_payment_id from that *specific*
    fiscal year's own generated term-of-payment scope -- proven here by
    round-tripping through the terms-of-payment endpoint for the same
    (client_id, fiscal_year_id), not just asserting the field's shape."""
    client_id = _fresh_id()
    records = _get_fiscal_years(client, client_id=client_id)
    assert records, "no fiscal-year records returned"

    for record in records:
        terms = client.get(
            TERMS_OF_PAYMENT_ENDPOINT.format(client_id=client_id, fiscal_year_id=record["id"]),
            headers=JSON_ACCEPT_HEADERS,
        ).json()
        term_ids = {int(term["id"]) for term in terms}
        assert record["creditor_term_of_payment_id"] in term_ids


# --- GET .../fiscal-years/{fiscal-year-id}/cost-systems ---


def test_cost_systems_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_COST_SYSTEMS, (
        f"expected at least {MIN_COST_SYSTEMS} cost-system records, got {len(records)}"
    )


def test_cost_system_record_has_core_fields(client):
    records = _get_cost_systems(client)
    assert records, "no cost-system records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and 1 <= len(record["id"]) <= 1
        assert isinstance(record.get("short_name"), str) and record["short_name"].strip()
        assert isinstance(record.get("is_activated_for_postings"), bool)
        # Spec types `number` as "number" (format "short") despite being an
        # integer-valued field in practice — see epic doc's quirk note.
        assert isinstance(record.get("number"), int)
        # `cost_field` is a real **int** field, confirmed by
        # `examples/cost-systems.xml` — corrected from an earlier,
        # unevidenced `Optional[str]` guess (epic
        # `datev-mock-real-data-reconciliation`, W2).
        assert isinstance(record.get("cost_field"), int)


def test_cost_systems_same_ids_are_stable(client):
    """P3 (decision #7): replaces the old *_ignores_*_id_values test. Same
    (client_id, fiscal_year_id) used twice must return identical data."""
    client_id, fiscal_year_id = _fresh_id(), _fresh_id()
    first = _get_cost_systems(client, client_id=client_id, fiscal_year_id=fiscal_year_id)
    second = _get_cost_systems(client, client_id=client_id, fiscal_year_id=fiscal_year_id)
    assert first == second


def test_cost_systems_different_ids_return_different_data(client):
    """Two different (client_id, fiscal_year_id) pairs must return
    different data. Retries a few fresh id pairs before failing -- only
    `is_activated_for_postings` (a per-record boolean) varies for this
    endpoint, so a couple of independently-random scopes have a small but
    non-negligible chance of coinciding on the very first draw."""
    first = _get_cost_systems(client, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    for _ in range(8):
        candidate = _get_cost_systems(client, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
        if candidate != first:
            return
    raise AssertionError("expected cost systems to differ across fresh client/fiscal-year ids")


# --- GET .../cost-systems/{cost-system-id}/cost-centers ---


def test_cost_centers_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
        ),
        headers=JSON_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_COST_CENTERS, (
        f"expected at least {MIN_COST_CENTERS} cost-center records, got {len(records)}"
    )


def test_cost_center_record_has_core_fields(client):
    records = _get_cost_centers(client)
    assert records, "no cost-center records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("long_name"), str) and record["long_name"].strip()
        assert isinstance(record.get("short_name"), str) and record["short_name"].strip()
        assert isinstance(record.get("creation_date"), str) and record["creation_date"].strip()


def test_cost_center_cost_rates_use_integer_encoded_dates(client):
    """`cost_rates[].valid_from`/`valid_to` are documented as integer-encoded
    dates (e.g. `20161201`), not date-time strings — an explicit epic-doc
    quirk, tested here rather than just noted."""
    records = _get_cost_centers(client)
    records_with_rates = [r for r in records if r.get("cost_rates")]
    assert records_with_rates, "no cost-center record carries a populated cost_rates entry"

    for record in records_with_rates:
        for rate in record["cost_rates"]:
            assert isinstance(rate.get("valid_from"), int) and _YYYYMMDD_RE.match(str(rate["valid_from"]))
            assert isinstance(rate.get("valid_to"), int) and _YYYYMMDD_RE.match(str(rate["valid_to"]))
            assert isinstance(rate.get("rate"), (int, float))


def test_cost_centers_same_ids_are_stable(client):
    """P3 (decision #7): replaces the old *_ignores_*_id_values test. Same
    (client_id, fiscal_year_id, cost_system_id) used twice must return
    identical data."""
    client_id, fiscal_year_id, cost_system_id = _fresh_id(), _fresh_id(), _fresh_id()
    first = _get_cost_centers(
        client, client_id=client_id, fiscal_year_id=fiscal_year_id, cost_system_id=cost_system_id
    )
    second = _get_cost_centers(
        client, client_id=client_id, fiscal_year_id=fiscal_year_id, cost_system_id=cost_system_id
    )
    assert first == second


def test_cost_centers_different_ids_return_different_data(client):
    """Two different (client_id, fiscal_year_id, cost_system_id) triples
    must return different data (`responsible`/`rate` vary continuously per
    scope, so the first fresh pair virtually always differs already)."""
    first = _get_cost_centers(
        client, client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
    )
    for _ in range(3):
        candidate = _get_cost_centers(
            client, client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
        )
        if candidate != first:
            return
    raise AssertionError(
        "expected cost centers to differ across fresh client/fiscal-year/cost-system ids"
    )


# --- XML content negotiation (epic `datev-mock-real-data-reconciliation`,
# W2) — same style as `tests/test_accounting.py`'s XML assertions for
# accounting.clients. `cost_systems`' root tag/namespace/repeated-element
# name are **confirmed** by `examples/cost-systems.xml`; `fiscal_years`' and
# `cost_centers`' are **inferred by pattern** (no direct real XML evidence).


def test_fiscal_years_xml_root_tag_and_namespace(client):
    response = client.get(
        FISCAL_YEARS_ENDPOINT.format(client_id=_fresh_id()), headers=XML_ACCEPT_HEADERS
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{FISCAL_YEAR_NS}}}ArrayOfFiscalYear"

    records = [child for child in root if _local_name(child.tag) == "FiscalYear"]
    assert len(records) >= MIN_FISCAL_YEARS

    first = records[0]
    assert _field(first, "AccountSystem").text is not None
    assert _field(first, "CurrencyCode").text is not None


def test_fiscal_years_xml_optional_field_uses_nil_when_absent(client):
    response = client.get(
        FISCAL_YEARS_ENDPOINT.format(client_id=_fresh_id()), headers=XML_ACCEPT_HEADERS
    )
    root = ET.fromstring(response.content)
    records = [child for child in root if _local_name(child.tag) == "FiscalYear"]

    nil_seen = any(_is_nil(_field(record, "LegalForm")) for record in records)
    assert nil_seen, "expected at least one FiscalYear record with LegalForm i:nil='true'"


def test_cost_systems_xml_root_tag_and_namespace(client):
    """Confirmed shape (`examples/cost-systems.xml`): root `ArrayOfCostSystems`,
    repeated child `CostSystems` (plural, not the generically-expected
    singular `CostSystem`)."""
    response = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{COST_SYSTEMS_NS}}}ArrayOfCostSystems"

    records = [child for child in root if _local_name(child.tag) == "CostSystems"]
    assert len(records) >= MIN_COST_SYSTEMS

    first = records[0]
    assert _field(first, "CostField").text is not None
    assert _field(first, "ShortName").text is not None
    assert _field(first, "IsActivatedForPostings").text in ("true", "false")


def test_cost_centers_xml_root_tag_and_namespace(client):
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
        ),
        headers=XML_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{COST_CENTER_NS}}}ArrayOfCostCenter"

    records = [child for child in root if _local_name(child.tag) == "CostCenter"]
    assert len(records) >= MIN_COST_CENTERS

    first = records[0]
    assert _field(first, "LongName").text is not None
    assert _field(first, "ShortName").text is not None


def test_cost_centers_xml_optional_field_uses_nil_when_absent(client):
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
        ),
        headers=XML_ACCEPT_HEADERS,
    )
    root = ET.fromstring(response.content)
    records = [child for child in root if _local_name(child.tag) == "CostCenter"]

    nil_seen = any(_is_nil(_field(record, "Note")) for record in records)
    assert nil_seen, "expected at least one CostCenter record with Note i:nil='true'"
