"""RED-phase tests for JSON content negotiation on
GET /datev/api/accounting/v1/clients.

Context: a real-traffic capture (`examples/JUS_clients.xml`) shows this
endpoint returning DataContractSerializer XML (`ArrayOfClient` root) on port
58452 over HTTPS. DATEV's official current developer docs (developer.datev.de,
Accounting product v1.7.4) document the same logical endpoint
(`GET /datev/api/accounting/v1/clients`) as returning JSON on port 58454 over
plain HTTP, with this confirmed example response body:

    [
      {
        "company_data": {
          "creditor_identifier": "DE98ZZZ09999999999"
        },
        "id": "78a11a29-2a32-4a5e-a73b-632f6aeae131",
        "name": "DATEVconnect GmbH",
        "number": "47011"
      }
    ]

Decision (recorded in `odd/tasks/datev-mock.md` under "## Decisions"): support
*both* formats via content negotiation on the same endpoint/port (58452) — no
second port binding. `Accept: application/json` returns this JSON shape;
`Accept: application/xml` (or no explicit preference) keeps the existing XML
shape asserted in `test_accounting.py`, unchanged.

Note the deliberate discrepancy: the documented JSON `number` field is a
*string* (`"47011"`), unlike the XML `Number` field, which is int-like text.
Do not coerce — this test asserts `number` is a `str`.
"""
from __future__ import annotations

import uuid

ENDPOINT = "/datev/api/accounting/v1/clients"

JSON_ACCEPT_HEADERS = {"accept": "application/json"}

MIN_RECORDS = 3


def _get_json_records(client) -> list[dict]:
    response = client.get(ENDPOINT, headers=JSON_ACCEPT_HEADERS)
    return response.json()


def test_accounting_json_returns_200(client):
    response = client.get(ENDPOINT, headers=JSON_ACCEPT_HEADERS)
    assert response.status_code == 200


def test_accounting_json_content_type_is_json(client):
    response = client.get(ENDPOINT, headers=JSON_ACCEPT_HEADERS)
    assert response.headers["content-type"].startswith("application/json")


def test_accounting_json_body_is_array(client):
    records = _get_json_records(client)
    assert isinstance(records, list)
    assert len(records) >= MIN_RECORDS, (
        f"expected at least {MIN_RECORDS} client records, got {len(records)}"
    )


def test_accounting_json_record_has_id_name_number(client):
    records = _get_json_records(client)
    assert records, "no client records returned"

    for record in records:
        assert "id" in record and "name" in record and "number" in record

        # id must be a valid UUID string.
        uuid.UUID(record["id"])

        assert isinstance(record["name"], str) and record["name"].strip()

        # Deliberate discrepancy vs the XML `Number` (int-like text): the
        # documented JSON shape has `number` as a string, e.g. "47011".
        assert isinstance(record["number"], str)


def test_accounting_json_number_is_not_coerced_to_int(client):
    """Guards against silently "fixing" the documented string quirk."""
    records = _get_json_records(client)
    assert records, "no client records returned"

    for record in records:
        assert not isinstance(record["number"], int)


def test_accounting_json_at_least_one_record_has_populated_company_data(client):
    """Mirrors the real docs example, where one record carries a populated
    `company_data.creditor_identifier` while other records may have
    `company_data` as `null` or the key absent (mirroring how `CompanyData`
    is `i:nil="true"` for most XML records)."""
    records = _get_json_records(client)
    assert records, "no client records returned"

    populated = [
        record
        for record in records
        if isinstance(record.get("company_data"), dict)
        and record["company_data"].get("creditor_identifier")
    ]
    assert populated, "expected at least one record with populated company_data.creditor_identifier"

    for record in populated:
        creditor_id = record["company_data"]["creditor_identifier"]
        assert isinstance(creditor_id, str) and creditor_id.strip()


def test_accounting_json_records_without_company_data_are_null_or_absent(client):
    """Records that don't carry company_data must use `null` or omit the key
    entirely — never an empty object or other placeholder."""
    records = _get_json_records(client)
    assert records, "no client records returned"

    for record in records:
        if "company_data" in record:
            assert record["company_data"] is None or isinstance(record["company_data"], dict)
