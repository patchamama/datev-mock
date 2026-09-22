"""RED-phase tests for GET /datev/api/accounting/v1/clients.

Asserts the mock reproduces the real DATEV `ArrayOfClient` DataContractSerializer
XML shape (Irw/Connect/Accounting contract): a flat list of `Client` elements,
each with 8 fields, `Id`/`ClientGuid` mirrored, `AccountingProductivities`/
`CompanyData` always nil, `Name`/`Number` populated.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

ACCOUNTING_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Clients"
)
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ARRAY_ROOT_TAG = f"{{{ACCOUNTING_NS}}}ArrayOfClient"
CLIENT_LOCAL_NAME = "Client"
NIL_ATTR = f"{{{XSI_NS}}}nil"

ENDPOINT = "/datev/api/accounting/v1/clients"

EXPECTED_FIELDS = [
    "Id",
    "Parent",
    "membersToSerialize",
    "AccountingProductivities",
    "ClientGuid",
    "CompanyData",
    "Name",
    "Number",
]

MIN_RECORDS = 3


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _get_root(client) -> ET.Element:
    response = client.get(ENDPOINT)
    return ET.fromstring(response.content)


def _clients(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if _local_name(child.tag) == CLIENT_LOCAL_NAME]


def _field(record: ET.Element, local_name: str) -> ET.Element:
    for child in record:
        if _local_name(child.tag) == local_name:
            return child
    raise AssertionError(f"expected field {local_name!r} not found on Client")


def _is_nil(field_el: ET.Element) -> bool:
    return field_el.get(NIL_ATTR) == "true"


def test_accounting_returns_200(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 200


def test_accounting_content_type_is_xml(client):
    response = client.get(ENDPOINT)
    assert response.headers["content-type"].startswith("application/xml")


def test_accounting_root_tag_matches_datev_contract(client):
    root = _get_root(client)
    assert root.tag == ARRAY_ROOT_TAG


def test_accounting_has_at_least_3_clients(client):
    root = _get_root(client)
    records = _clients(root)
    assert len(records) >= MIN_RECORDS, (
        f"expected at least {MIN_RECORDS} Client records, got {len(records)}"
    )


def test_each_client_has_all_expected_fields(client):
    root = _get_root(client)
    records = _clients(root)
    assert records, "no Client records returned"

    for record in records:
        present_local_names = {_local_name(child.tag) for child in record}
        missing = set(EXPECTED_FIELDS) - present_local_names
        assert not missing, f"Client missing fields: {sorted(missing)}"


def test_id_and_client_guid_are_mirrored(client):
    root = _get_root(client)
    records = _clients(root)

    for record in records:
        id_el = _field(record, "Id")
        guid_el = _field(record, "ClientGuid")
        assert not _is_nil(id_el) and id_el.text
        assert not _is_nil(guid_el) and guid_el.text
        assert id_el.text == guid_el.text, (
            f"Id ({id_el.text!r}) must equal ClientGuid ({guid_el.text!r})"
        )


def test_accounting_productivities_and_company_data_are_nil(client):
    root = _get_root(client)
    records = _clients(root)

    for record in records:
        productivities_el = _field(record, "AccountingProductivities")
        company_data_el = _field(record, "CompanyData")
        assert _is_nil(productivities_el), "AccountingProductivities must be i:nil='true'"
        assert _is_nil(company_data_el), "CompanyData must be i:nil='true'"


def test_name_and_number_are_populated(client):
    root = _get_root(client)
    records = _clients(root)

    for record in records:
        name_el = _field(record, "Name")
        number_el = _field(record, "Number")
        assert not _is_nil(name_el) and name_el.text and name_el.text.strip()
        assert not _is_nil(number_el)
        # Raises ValueError on non-numeric text - that is itself a test failure.
        int(number_el.text)
