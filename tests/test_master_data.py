"""RED-phase tests for GET /datev/api/master-data/v1/clients.

Asserts the mock reproduces the real DATEV `ArrayOfClientResource`
DataContractSerializer XML shape (Sdd/Connect contract): a flat list of
`ClientResource` elements, each with the exact 41-field layout observed in
`examples/clients.xml`, most fields `i:nil="true"` in the sparse fake
dataset just like the real sample.
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime

MASTER_DATA_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Sdd.Connect.PlugIn.Contracts.Resources"
)
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ARRAY_ROOT_TAG = f"{{{MASTER_DATA_NS}}}ArrayOfClientResource"
CLIENT_RESOURCE_LOCAL_NAME = "ClientResource"
NIL_ATTR = f"{{{XSI_NS}}}nil"

ENDPOINT = "/datev/api/master-data/v1/clients"

# Exact child-element order confirmed against the real sample shape (task spec).
EXPECTED_FIELDS = [
    "Id",
    "Parent",
    "membersToSerialize",
    "AccountHolderForBilling",
    "AuthorizedRecipientForLegalPerson",
    "AuthorizedRecipientForNaturalPerson",
    "ClientSince",
    "ClientTo",
    "CorrespondenceRecipient",
    "DifferingName",
    "EstablishmentId",
    "EstablishmentName",
    "EstablishmentNumber",
    "EstablishmentShortName",
    "FunctionalAreaId",
    "FunctionalAreaName",
    "FunctionalAreaShortName",
    "IdentificationCheckedOn",
    "IdentificationComment",
    "IdentificationStatus",
    "InvoiceRecipients",
    "LeadId",
    "LegalPersonId",
    "Name",
    "NaturalPersonId",
    "Note",
    "Number",
    "OnlineRevision",
    "OrganizationId",
    "OrganizationName",
    "OrganizationNumber",
    "Revision",
    "RiskAssessment",
    "RiskAssessmentDate",
    "RiskAssessmentReason",
    "Status",
    "StayRegistered",
    "Timestamp",
    "TransparencyRegister",
    "TransparencyRegisterCheckedOn",
    "TransparencyRegisterComment",
    "Type",
]

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

MIN_RECORDS = 15


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _get_root(client) -> ET.Element:
    response = client.get(ENDPOINT)
    return ET.fromstring(response.content)


def _client_resources(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if _local_name(child.tag) == CLIENT_RESOURCE_LOCAL_NAME]


def _field(record: ET.Element, local_name: str) -> ET.Element:
    for child in record:
        if _local_name(child.tag) == local_name:
            return child
    raise AssertionError(f"expected field {local_name!r} not found on ClientResource")


def _is_nil(field_el: ET.Element) -> bool:
    return field_el.get(NIL_ATTR) == "true"


def test_master_data_returns_200(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 200


def test_master_data_content_type_is_xml(client):
    response = client.get(ENDPOINT)
    assert response.headers["content-type"].startswith("application/xml")


def test_master_data_root_tag_matches_datev_contract(client):
    root = _get_root(client)
    assert root.tag == ARRAY_ROOT_TAG


def test_master_data_has_at_least_15_clients(client):
    root = _get_root(client)
    records = _client_resources(root)
    assert len(records) >= MIN_RECORDS, (
        f"expected at least {MIN_RECORDS} ClientResource records, got {len(records)}"
    )


def test_each_client_resource_has_all_expected_fields(client):
    root = _get_root(client)
    records = _client_resources(root)
    assert records, "no ClientResource records returned"

    for record in records:
        present_local_names = {_local_name(child.tag) for child in record}
        missing = set(EXPECTED_FIELDS) - present_local_names
        assert not missing, f"ClientResource missing fields: {sorted(missing)}"


def test_client_numbers_are_unique_ints(client):
    root = _get_root(client)
    records = _client_resources(root)

    numbers = []
    for record in records:
        number_el = _field(record, "Number")
        assert not _is_nil(number_el), "Number must be populated, not nil"
        numbers.append(int(number_el.text))

    assert len(numbers) == len(set(numbers)), "Number values must be unique across clients"


def test_client_status_and_type_are_non_empty(client):
    root = _get_root(client)
    records = _client_resources(root)

    for record in records:
        status_el = _field(record, "Status")
        type_el = _field(record, "Type")
        assert not _is_nil(status_el) and status_el.text and status_el.text.strip()
        assert not _is_nil(type_el) and type_el.text and type_el.text.strip()


def test_client_timestamp_is_iso8601(client):
    root = _get_root(client)
    records = _client_resources(root)

    for record in records:
        timestamp_el = _field(record, "Timestamp")
        assert not _is_nil(timestamp_el)
        # Raises ValueError on malformed input - that is itself a test failure.
        datetime.fromisoformat(timestamp_el.text)


def test_client_id_is_valid_guid(client):
    root = _get_root(client)
    records = _client_resources(root)

    for record in records:
        id_el = _field(record, "Id")
        assert not _is_nil(id_el)
        assert UUID_RE.match(id_el.text), f"Id {id_el.text!r} is not a valid GUID"
        uuid.UUID(id_el.text)


def test_at_least_one_unpopulated_field_uses_xsi_nil(client):
    root = _get_root(client)
    records = _client_resources(root)

    nil_candidates = ("Note", "RiskAssessment")
    found_nil = False
    for record in records:
        for local_name in nil_candidates:
            field_el = _field(record, local_name)
            if _is_nil(field_el):
                found_nil = True
                assert field_el.text is None, (
                    f"{local_name} marked i:nil='true' must have no text content"
                )

    assert found_nil, (
        f"expected at least one record with i:nil='true' on one of {nil_candidates}"
    )


# --- real-data reconciliation epic, W4: JSON content negotiation ---
#
# Real evidence (`examples/master-data-clients.xml`, JSON content despite
# the `.xml` filename, 100 records): a simplified JSON projection exists
# alongside the already-modeled 42-field XML. The epic doc's own field table
# (from a compiled first-record summary) listed 7 always-present fields; W4
# found 2 more real, genuinely optional fields (`client_since`/`client_to`)
# by counting occurrences across the full file — both included here.

# `legal_person_id` was 100%-present in the real 100-record sample, but that
# sample happened to be 100% `legal_person`-typed (a single-client-type
# sample artifact). This mock's pre-existing (unmodified by this task)
# `ClientResource` fake-data generator legitimately leaves `legal_person_id`
# unset on some records independent of `type` — genuinely optional for this
# mock's mixed dataset, so it's asserted as optional here, not required.
_ALWAYS_PRESENT_JSON_FIELDS = {"id", "name", "number", "status", "timestamp", "type"}
_OPTIONAL_JSON_FIELDS = {"legal_person_id", "client_since", "client_to"}


def test_master_data_clients_json_content_type_when_accept_json(client):
    response = client.get(ENDPOINT, headers={"accept": "application/json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_master_data_clients_json_records_have_core_fields(client):
    response = client.get(ENDPOINT, headers={"accept": "application/json"})
    records = response.json()
    assert isinstance(records, list) and records

    for record in records:
        missing = _ALWAYS_PRESENT_JSON_FIELDS - set(record.keys())
        assert not missing, f"master-data client JSON record missing fields: {sorted(missing)}"
        # Only the 6 always-present fields plus the confirmed-optional ones
        # may appear — never an untracked/leaked field.
        assert set(record.keys()) <= _ALWAYS_PRESENT_JSON_FIELDS | _OPTIONAL_JSON_FIELDS


def test_master_data_clients_json_legal_person_id_present_on_at_least_one_record(client):
    """Real evidence confirms the field exists and is populated (100/100 in
    the sample) — not asserted as unconditionally required here (see the
    module-level note), but the fake dataset must exercise it at least
    once."""
    response = client.get(ENDPOINT, headers={"accept": "application/json"})
    records = response.json()
    assert any("legal_person_id" in record for record in records), (
        "expected at least one master-data client JSON record with legal_person_id"
    )


def test_master_data_clients_json_number_is_a_real_int_not_a_string(client):
    """Real evidence confirms `number` is an unquoted JSON int on every
    sampled record (same precedent as accounting.clients' W1 fix)."""
    response = client.get(ENDPOINT, headers={"accept": "application/json"})
    records = response.json()
    assert records, "no master-data client records returned"

    for record in records:
        assert isinstance(record["number"], int)
        assert not isinstance(record["number"], bool)


def test_master_data_clients_default_format_is_still_xml(client):
    """Ambiguous/missing Accept keeps the pre-existing XML default (same
    live default_accounting_format mechanism every other negotiated
    endpoint uses)."""
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
