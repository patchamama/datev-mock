"""RED-phase tests for `app/overrides.py`'s endpoint-override detection and
in-memory storage contract.

`app/overrides.py` does not exist yet — this file is expected to fail on
collection with `ModuleNotFoundError` until V1-GREEN implements it. See
`odd/tasks/datev-mock-custom-overrides.md` for the authoritative design
(endpoint-key table, fingerprint fields, ambiguous groups).

## Contract under test (settled here, for the GREEN implementer)

- `detect_candidates(content: str) -> list[str]` — two-pass detection
  (try XML root tag first, then JSON fingerprint field-set). Returns a
  list of endpoint keys: `[]` (no match), one key (unambiguous), or
  2-3 keys (one of the three structurally-identical DATEV resource
  groups: creditors/debitors; accounts_payable/accounts_payable_condense/
  accounts_receivable_condense; posting_proposal_rules_incoming/outgoing).
- `set_override(key: str, content: str, content_type: str, filename: str) -> None`
  — stores/replaces an override for `key`, `enabled=True` by default.
- `get_active_override(key: str) -> Override | None` — returns the stored
  `Override` (with `.content`, `.content_type`, `.filename`,
  `.uploaded_at`, `.enabled` attributes) only if `enabled` is `True`,
  else `None` (including when nothing is stored for `key` at all).
- `list_overrides() -> dict[str, dict]` — every stored override (enabled
  or not), keyed by endpoint key; each value carries at least `content_type`,
  `filename`, `uploaded_at`, `enabled`.
- `set_enabled(key: str, enabled: bool) -> None` — toggles a stored
  override without deleting it.
- `delete_override(key: str) -> None` — removes the override entirely.
- `clear_all_overrides() -> None` — test-only helper; wipes all stored and
  pending state. Used here and by `tests/test_overrides_api.py`'s local
  isolation fixture.

`master_data.addressees/{id}` is deliberately never used as a detection
target anywhere below — it is excluded from the override feature entirely
(see the task doc's scope boundaries).
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from app import overrides

# --- isolation ---


@pytest.fixture(autouse=True)
def _clear_overrides():
    overrides.clear_all_overrides()
    yield
    overrides.clear_all_overrides()


def _json_content(records: list[dict]) -> str:
    return json.dumps(records)


# --- XML detection (3 known root tags) ---


def test_detect_echo_xml_root_tag():
    content = "<Echo><echo_message>hello</echo_message><id>abc-123</id></Echo>"
    assert overrides.detect_candidates(content) == ["diagnostics.echo"]


def test_detect_master_data_clients_xml_root_tag():
    content = "<ArrayOfClientResource></ArrayOfClientResource>"
    assert overrides.detect_candidates(content) == ["master_data.clients"]


def test_detect_accounting_clients_xml_root_tag():
    content = "<ArrayOfClient></ArrayOfClient>"
    assert overrides.detect_candidates(content) == ["accounting.clients"]


# --- JSON detection, unambiguous cases ---


def test_detect_accounting_clients_json():
    content = _json_content(
        [
            {"id": "1", "name": "Acme GmbH", "number": "70000", "extra": "x"},
            {"id": "2", "name": "Beta AG", "number": "70001", "company_data": None},
        ]
    )
    assert overrides.detect_candidates(content) == ["accounting.clients"]


def test_detect_master_data_addressees_json():
    content = _json_content(
        [
            {
                "type": "legal_person",
                "status": "active",
                "timestamp": "2026-01-01T00:00:00Z",
                "current_company_name": "Acme GmbH",
                "extra_field": "irrelevant",
            },
            {
                "type": "natural_person",
                "status": "active",
                "timestamp": "2026-01-02T00:00:00Z",
                "firstname": "Max",
            },
        ]
    )
    assert overrides.detect_candidates(content) == ["master_data.addressees"]


def test_detect_master_data_banks_json():
    content = _json_content(
        [
            {
                "bic": "GENODEF1M01",
                "country_code": "DE",
                "bank_code": "12345678",
                "name": "Testbank",
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == ["master_data.banks"]


def test_detect_accounting_fiscal_years_json():
    content = _json_content(
        [
            {
                "account_system": 4,
                "currency_code": "EUR",
                "legal_form": "gmbh",
                "taxation_method": "regular",
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == ["accounting.fiscal_years"]


def test_detect_accounting_cost_systems_json():
    content = _json_content(
        [{"short_name": "KOST1", "is_activated_for_postings": True, "extra": "x"}]
    )
    assert overrides.detect_candidates(content) == ["accounting.cost_systems"]


def test_detect_accounting_cost_centers_json():
    content = _json_content(
        [
            {
                "long_name": "Marketing",
                "short_name": "MKT",
                "creation_date": "2026-01-01",
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == ["accounting.cost_centers"]


def test_detect_accounting_general_ledger_accounts_json():
    content = _json_content(
        [
            {
                "account_number": 8400,
                "caption": "Erloese",
                "main_function": 1,
                "main_function_number": 2,
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == ["accounting.general_ledger_accounts"]


def test_detect_accounting_accounting_sequences_processed_json():
    content = _json_content(
        [
            {
                "accounting_sequence_id": "seq-1",
                "record_type": "invoice",
                "accounting_reason": "posting",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == [
        "accounting.accounting_sequences_processed"
    ]


def test_detect_accounting_accounting_transaction_keys_json():
    content = _json_content(
        [{"tax_rate": 19.0, "is_tax_rate_selectable": False, "extra": "x"}]
    )
    assert overrides.detect_candidates(content) == ["accounting.accounting_transaction_keys"]


def test_detect_accounting_assets_stocktakings_json():
    content = _json_content(
        [{"asset_number": 100, "inventory_number": "INV-1", "extra": "x"}]
    )
    assert overrides.detect_candidates(content) == ["accounting.assets_stocktakings"]


def test_detect_accounting_terms_of_payment_json():
    content = _json_content(
        [{"caption": "30 days net", "due_type": "due_in_days", "extra": "x"}]
    )
    assert overrides.detect_candidates(content) == ["accounting.terms_of_payment"]


def test_detect_dms_domains_json():
    content = _json_content(
        [
            {"name": "Root", "type": "domain", "extra": "x"},
            {"name": "Invoices", "type": "folder", "extra": "y"},
        ]
    )
    assert overrides.detect_candidates(content) == ["dms.domains"]


def test_detect_dms_documents_json():
    content = _json_content(
        [
            {
                "amount": 199.99,
                "document_class": "invoice",
                "domain_id": "dom-1",
                "created_at": "2026-01-01T00:00:00Z",
                "modified_at": "2026-01-02T00:00:00Z",
                "extra": "x",
            }
        ]
    )
    assert overrides.detect_candidates(content) == ["dms.documents"]


# --- JSON detection, ambiguous groups (3 total) ---


def test_detect_creditor_debitor_fingerprint_is_ambiguous():
    content = _json_content(
        [
            {
                "addressee_id": "addr-1",
                "business_partner_number": "70000",
                "legal_entity_type": "natural_person",
                "extra": "x",
            }
        ]
    )
    assert set(overrides.detect_candidates(content)) == {
        "accounting.creditors",
        "accounting.debitors",
    }


def test_detect_open_item_fingerprint_is_ambiguous():
    content = _json_content(
        [
            {
                "amount_debit": 100.0,
                "amount_credit": 0.0,
                "evidence_type": "invoice",
                "debit_credit_identifier": "debit",
                "extra": "x",
            }
        ]
    )
    assert set(overrides.detect_candidates(content)) == {
        "accounting.accounts_payable",
        "accounting.accounts_payable_condense",
        "accounting.accounts_receivable_condense",
    }


def test_detect_posting_proposal_rule_fingerprint_is_ambiguous():
    content = _json_content(
        [
            {
                "assignment_criteria": {"name": "x", "tax_rate": 19.0},
                "posting_proposal_information": [],
                "uncertain_label": False,
                "extra": "x",
            }
        ]
    )
    assert set(overrides.detect_candidates(content)) == {
        "accounting.posting_proposal_rules_incoming",
        "accounting.posting_proposal_rules_outgoing",
    }


# --- no match ---


def test_detect_no_match_for_unrecognized_json():
    assert overrides.detect_candidates('{"foo": "bar"}') == []


def test_detect_no_match_for_non_xml_non_json_text():
    assert overrides.detect_candidates("just some random text, not xml or json") == []


# --- storage round-trip ---


def test_set_override_then_get_active_returns_enabled_by_default():
    overrides.set_override(
        "master_data.banks", '[{"bic": "X"}]', "json", "banks.json"
    )

    result = overrides.get_active_override("master_data.banks")

    assert result is not None
    assert result.enabled is True
    assert result.content == '[{"bic": "X"}]'
    assert result.content_type == "json"
    assert result.filename == "banks.json"


def test_set_enabled_false_hides_from_active_but_keeps_in_list():
    overrides.set_override(
        "master_data.banks", '[{"bic": "X"}]', "json", "banks.json"
    )

    overrides.set_enabled("master_data.banks", False)

    assert overrides.get_active_override("master_data.banks") is None

    listing = overrides.list_overrides()
    assert "master_data.banks" in listing
    assert listing["master_data.banks"]["enabled"] is False


def test_delete_override_removes_it_from_list_entirely():
    overrides.set_override(
        "master_data.banks", '[{"bic": "X"}]', "json", "banks.json"
    )

    overrides.delete_override("master_data.banks")

    assert "master_data.banks" not in overrides.list_overrides()


# --- sanitize_xml: bare-ampersand repair ---
#
# Regression coverage for a real bug: real-world captured DATEV XML (unlike
# this mock's own serializer output) has been observed with a bare,
# unescaped "&" in text content -- e.g. a company name like
# "GSBW Koop & Sch" -- which is technically invalid XML that the strict
# stdlib parser rejects outright, so detection silently failed with "no
# candidates" for otherwise-perfectly-recognizable real DATEV files.


def test_sanitize_xml_repairs_a_bare_ampersand():
    broken = "<ArrayOfClient><Client><Name>GSBW Koop & Sch</Name></Client></ArrayOfClient>"

    repaired = overrides.sanitize_xml(broken)

    assert "GSBW Koop &amp; Sch" in repaired
    ET.fromstring(repaired)  # must now parse cleanly


def test_sanitize_xml_leaves_already_valid_xml_unchanged():
    valid = "<Echo><echo_message>hi &amp; bye</echo_message></Echo>"

    assert overrides.sanitize_xml(valid) == valid


def test_sanitize_xml_does_not_double_escape_existing_entities():
    valid_with_entities = (
        "<Echo><echo_message>a &amp; b &lt;tag&gt; &#39;q&#39;</echo_message></Echo>"
    )

    result = overrides.sanitize_xml(valid_with_entities)

    assert result == valid_with_entities
    assert "&amp;amp;" not in result


def test_detect_candidates_recognizes_xml_with_a_bare_ampersand():
    broken = (
        '<ArrayOfClientResource xmlns="http://schemas.datacontract.org/2004/07/'
        'Datev.Sdd.Connect.PlugIn.Contracts.Resources">'
        "<ClientResource><Name>GSBW Koop & Sch</Name></ClientResource>"
        "</ArrayOfClientResource>"
    )

    assert overrides.detect_candidates(broken) == ["master_data.clients"]
