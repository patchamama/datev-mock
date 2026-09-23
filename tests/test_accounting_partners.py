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
  `legal_entity_type` enum (`not_specified`/`natural_person`/`legal_person`).
  Correction (epic `datev-mock-real-data-reconciliation`, W1, real evidence
  from `examples/creditors.xml`): the co-located `natural_person`/
  `legal_person`/`not_specified_person` sibling objects this project
  originally invented never appear in the observed real default (non-
  `expand`) response — they are deliberately left unpopulated (`None`) now,
  not "gated only by description text" as originally assumed.
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
import xml.etree.ElementTree as ET

from app.routers.accounting import CREDITORS_ENDPOINT, DEBITORS_ENDPOINT

MIN_CREDITORS = 3
MIN_DEBITORS = 3

_LEGAL_ENTITY_TYPE_VALUES = {"not_specified", "natural_person", "legal_person"}

# Content negotiation (epic `datev-mock-real-data-reconciliation`, W2):
# creditors/debitors now default to XML (same mechanism as accounting.clients)
# when the Accept header doesn't explicitly request JSON.
JSON_ACCEPT_HEADERS = {"accept": "application/json"}
XML_ACCEPT_HEADERS = {"accept": "application/xml"}

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NIL_ATTR = f"{{{XSI_NS}}}nil"
BUSINESS_PARTNERS_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.BusinessPartners"
)


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


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _field(record: ET.Element, local_name: str) -> ET.Element:
    for child in record:
        if _local_name(child.tag) == local_name:
            return child
    raise AssertionError(f"expected field {local_name!r} not found")


def _is_nil(field_el: ET.Element) -> bool:
    return field_el.get(NIL_ATTR) == "true"


def _assert_business_partner_core_fields(record: dict) -> None:
    assert isinstance(record.get("id"), str) and record["id"].strip()
    assert isinstance(record.get("account_number"), int)
    assert isinstance(record.get("addressee_id"), str) and record["addressee_id"].strip()
    assert isinstance(record.get("business_partner_number"), str) and record["business_partner_number"].strip()
    assert record.get("legal_entity_type") in _LEGAL_ENTITY_TYPE_VALUES
    assert isinstance(record.get("short_name"), str) and record["short_name"].strip()
    # Real 13-field shape (epic `datev-mock-real-data-reconciliation`, W2,
    # `examples/creditors.xml`/`examples/debitors.xml`) — 11 always-present
    # fields, checked here beyond the pre-existing 5 above.
    assert isinstance(record.get("business_partner_relation_id"), str) and record[
        "business_partner_relation_id"
    ].strip()
    assert isinstance(record.get("caption"), str) and record["caption"].strip()
    assert isinstance(record.get("date_last_modification"), str) and record[
        "date_last_modification"
    ].strip()
    assert isinstance(record.get("is_business_partner_active"), bool)
    assert isinstance(record.get("is_organization_business_partner"), bool)


# --- GET .../fiscal-years/{fiscal-year-id}/creditors ---


def test_creditors_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        CREDITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
    )
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


def test_natural_person_creditors_do_not_populate_nested_natural_person(client):
    """Corrected per real evidence (epic `datev-mock-real-data-reconciliation`,
    W1): this test previously asserted a populated `natural_person` nested
    sub-object, which this project invented without evidence. Real captured
    evidence (`examples/creditors.xml`) shows the observed real record never
    carries `natural_person` at the top level of the default (non-`expand`)
    response, so it must be absent (or `None`), not populated."""
    records = _get(client, CREDITORS_ENDPOINT)
    natural_person_records = [r for r in records if r.get("legal_entity_type") == "natural_person"]
    assert natural_person_records, "no natural_person creditor records returned"

    for record in natural_person_records:
        assert record.get("natural_person") is None


def test_legal_person_creditors_do_not_populate_nested_legal_person(client):
    """Corrected per real evidence (epic `datev-mock-real-data-reconciliation`,
    W1): this test previously asserted a populated `legal_person` nested
    sub-object, which this project invented without evidence. Real captured
    evidence (`examples/creditors.xml`) shows the observed real record never
    carries `legal_person` at the top level of the default (non-`expand`)
    response, so it must be absent (or `None`), not populated."""
    records = _get(client, CREDITORS_ENDPOINT)
    legal_person_records = [r for r in records if r.get("legal_entity_type") == "legal_person"]
    assert legal_person_records, "no legal_person creditor records returned"

    for record in legal_person_records:
        assert record.get("legal_person") is None


def test_creditors_do_not_populate_accounting_information(client):
    """Real evidence (`examples/debitors.xml`, real XML) shows
    `AccountingInformation` always `i:nil="true"` even though it's a real,
    spec-derived field (unlike `natural_person`/`legal_person`, this project
    previously did populate it) — corrected per epic
    `datev-mock-real-data-reconciliation`, W2: `accounting_information` stays
    unpopulated by default, matching the confirmed real behavior."""
    records = _get(client, CREDITORS_ENDPOINT)
    assert records, "no creditor records returned"

    for record in records:
        assert record.get("accounting_information") is None


def test_creditor_eu_vat_fields_are_genuinely_optional(client):
    """`eu_vat_id_country_code`/`eu_vat_id_number` are the only 2 genuinely
    optional fields in the real 13-field shape — at least one record must
    carry them and at least one must lack them."""
    records = _get(client, CREDITORS_ENDPOINT)
    present = [r for r in records if "eu_vat_id_country_code" in r]
    absent = [r for r in records if "eu_vat_id_country_code" not in r]
    assert present, "expected at least one creditor record with eu_vat_id_country_code present"
    assert absent, "expected at least one creditor record with eu_vat_id_country_code absent"


def test_creditors_ignores_path_param_values(client):
    first = _get(client, CREDITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get(client, CREDITORS_ENDPOINT, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/debitors ---


def test_debitors_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        DEBITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=JSON_ACCEPT_HEADERS,
    )
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


def test_debitors_do_not_populate_accounting_information(client):
    """Real evidence (`examples/debitors.xml`, real XML): `AccountingInformation`
    is always `i:nil="true"` — corrected per epic
    `datev-mock-real-data-reconciliation`, W2, same as creditors above."""
    records = _get(client, DEBITORS_ENDPOINT)
    assert records, "no debitor records returned"

    for record in records:
        assert record.get("accounting_information") is None


# --- XML content negotiation (epic `datev-mock-real-data-reconciliation`,
# W2) — **confirmed** for `debitors` (`examples/debitors.xml`, real XML);
# `creditors`' XML shape is **inferred by pattern** from debitors' confirmed
# evidence (same `BusinessPartners` contract family, never directly observed
# in real XML itself).


def test_debitors_xml_root_tag_and_namespace(client):
    response = client.get(
        DEBITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{BUSINESS_PARTNERS_NS}}}ArrayOfDebitor"

    records = [child for child in root if _local_name(child.tag) == "Debitor"]
    assert len(records) >= MIN_DEBITORS

    first = records[0]
    assert _field(first, "AccountNumber").text is not None
    assert _field(first, "ShortName").text is not None
    assert _field(first, "IsBusinessPartnerActive").text in ("true", "false")


def test_debitors_xml_always_nil_fields_use_nil(client):
    """Locks in the always-nil field list confirmed by
    `examples/debitors.xml`: `AccountingInformation`/`NaturalPerson`/
    `LegalPerson` never populated by fake data, so every record must render
    `i:nil="true"` for them."""
    response = client.get(
        DEBITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    root = ET.fromstring(response.content)
    records = [child for child in root if _local_name(child.tag) == "Debitor"]
    assert records, "no Debitor records returned"

    for record in records:
        assert _is_nil(_field(record, "AccountingInformation"))
        assert _is_nil(_field(record, "NaturalPerson"))
        assert _is_nil(_field(record, "LegalPerson"))


def test_creditors_xml_root_tag_and_namespace(client):
    response = client.get(
        CREDITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(response.content)
    assert root.tag == f"{{{BUSINESS_PARTNERS_NS}}}ArrayOfCreditor"

    records = [child for child in root if _local_name(child.tag) == "Creditor"]
    assert len(records) >= MIN_CREDITORS

    first = records[0]
    assert _field(first, "AccountNumber").text is not None
    assert _field(first, "ShortName").text is not None


def test_creditors_xml_optional_field_uses_nil_when_absent(client):
    response = client.get(
        CREDITORS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id()),
        headers=XML_ACCEPT_HEADERS,
    )
    root = ET.fromstring(response.content)
    records = [child for child in root if _local_name(child.tag) == "Creditor"]

    nil_seen = any(_is_nil(_field(record, "EuVatIdCountryCode")) for record in records)
    assert nil_seen, "expected at least one Creditor record with EuVatIdCountryCode i:nil='true'"
