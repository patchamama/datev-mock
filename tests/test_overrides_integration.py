"""RED+GREEN tests for router integration (V3): confirms the real public
GET endpoints actually serve an active override, and fall back to normal
generated data once the override is disabled.

This is the payoff step: `app/overrides.py` (storage/detection) and the
`/admin/api/overrides*` admin API already work (V0-V2), but until V3 wires
the override check into `diagnostics.py`, `master_data.py`, `accounting.py`,
and `dms.py`, every public GET endpoint still returns its normal generated
data regardless of an enabled override. That's exactly what this file
exercises end-to-end through the real HTTP admin flow (upload -> resolve if
ambiguous -> GET public endpoint -> disable -> GET again), not by calling
`app.overrides` functions directly.

Covers a representative sample across all 4 router files:
- diagnostics.echo (XML)
- master_data.clients (XML), master_data.banks (JSON)
- accounting.clients (both XML-override and JSON-override cases, confirming
  an active override ignores the Accept header entirely)
- one endpoint from each of the 3 ambiguous groups, resolved via
  `/admin/api/overrides/resolve`: accounting.creditors,
  accounting.accounts_payable, accounting.posting_proposal_rules_incoming
- dms.domains (JSON)

See `odd/tasks/datev-mock-custom-overrides.md` for the full design.
"""
from __future__ import annotations

import json

import pytest

from app import overrides

OVERRIDES_ENDPOINT = "/admin/api/overrides"
RESOLVE_ENDPOINT = "/admin/api/overrides/resolve"


@pytest.fixture(autouse=True)
def _clear_overrides():
    overrides.clear_all_overrides()
    yield
    overrides.clear_all_overrides()


def _upload(client, filename: str, content: bytes, mime: str) -> dict:
    response = client.post(
        OVERRIDES_ENDPOINT,
        files={"file": (filename, content, mime)},
    )
    assert response.status_code == 200
    return response.json()


def _disable(client, key: str) -> None:
    response = client.put(f"{OVERRIDES_ENDPOINT}/{key}", json={"enabled": False})
    assert response.status_code == 200


# --- diagnostics.echo (XML) ---


def test_diagnostics_echo_serves_active_override_and_falls_back_when_disabled(client):
    override_xml = '<Echo><echo_message>custom</echo_message><id>custom-id</id></Echo>'

    result = _upload(client, "echo.xml", override_xml.encode("utf-8"), "application/xml")
    assert result == {"status": "matched", "endpoint": "diagnostics.echo"}

    response = client.get("/datev/api/diagnostics/v1/echo")
    assert response.text == override_xml
    assert "application/xml" in response.headers["content-type"]

    _disable(client, "diagnostics.echo")

    response = client.get("/datev/api/diagnostics/v1/echo")
    assert response.text != override_xml
    assert "custom-id" not in response.text


# --- master_data.clients (XML), master_data.banks (JSON) ---


def test_master_data_clients_serves_active_override_and_falls_back_when_disabled(client):
    override_xml = (
        "<ArrayOfClientResource><ClientResource><Id>custom-client</Id>"
        "</ClientResource></ArrayOfClientResource>"
    )

    result = _upload(client, "clients.xml", override_xml.encode("utf-8"), "application/xml")
    assert result == {"status": "matched", "endpoint": "master_data.clients"}

    response = client.get("/datev/api/master-data/v1/clients")
    assert response.text == override_xml
    assert "application/xml" in response.headers["content-type"]

    _disable(client, "master_data.clients")

    response = client.get("/datev/api/master-data/v1/clients")
    assert response.text != override_xml
    assert "custom-client" not in response.text


def test_master_data_banks_serves_active_override_and_falls_back_when_disabled(client):
    override_json = json.dumps([{"bic": "CUSTOMBIC1", "country_code": "ZZ"}])

    result = _upload(client, "banks.json", override_json.encode("utf-8"), "application/json")
    assert result == {"status": "matched", "endpoint": "master_data.banks"}

    response = client.get("/datev/api/master-data/v1/banks")
    assert response.json() == json.loads(override_json)
    assert "application/json" in response.headers["content-type"]

    _disable(client, "master_data.banks")

    response = client.get("/datev/api/master-data/v1/banks")
    assert response.json() != json.loads(override_json)


# --- accounting.clients: XML-override and JSON-override, Accept header ignored ---


def test_accounting_clients_json_override_ignores_accept_header_and_falls_back(client):
    override_json = json.dumps([{"id": "custom-1", "name": "Custom Corp", "number": "999"}])

    result = _upload(client, "clients.json", override_json.encode("utf-8"), "application/json")
    assert result == {"status": "matched", "endpoint": "accounting.clients"}

    # Even though Accept explicitly asks for XML, the JSON override wins.
    response = client.get(
        "/datev/api/accounting/v1/clients", headers={"Accept": "application/xml"}
    )
    assert response.json() == json.loads(override_json)
    assert "application/json" in response.headers["content-type"]

    _disable(client, "accounting.clients")

    response = client.get(
        "/datev/api/accounting/v1/clients", headers={"Accept": "application/xml"}
    )
    assert "application/xml" in response.headers["content-type"]
    assert response.text != override_json


def test_accounting_clients_xml_override_ignores_accept_header(client):
    override_xml = "<ArrayOfClient><Client><Id>custom-2</Id></Client></ArrayOfClient>"

    result = _upload(client, "clients.xml", override_xml.encode("utf-8"), "application/xml")
    assert result == {"status": "matched", "endpoint": "accounting.clients"}

    # Even though Accept explicitly asks for JSON, the XML override wins.
    response = client.get(
        "/datev/api/accounting/v1/clients", headers={"Accept": "application/json"}
    )
    assert response.text == override_xml
    assert "application/xml" in response.headers["content-type"]


# --- ambiguous groups, resolved via /admin/api/overrides/resolve ---


def test_accounting_creditors_ambiguous_group_resolved_and_served(client):
    override_json = json.dumps(
        [
            {
                "addressee_id": "addr-custom",
                "business_partner_number": "70099",
                "legal_entity_type": "natural_person",
            }
        ]
    )

    upload = _upload(
        client, "creditor_or_debitor.json", override_json.encode("utf-8"), "application/json"
    )
    assert upload["status"] == "ambiguous"
    assert set(upload["candidates"]) == {"accounting.creditors", "accounting.debitors"}

    resolve = client.post(
        RESOLVE_ENDPOINT,
        json={"pending_id": upload["pending_id"], "endpoint": "accounting.creditors"},
    )
    assert resolve.status_code == 200

    endpoint = "/datev/api/accounting/v1/clients/c1/fiscal-years/f1/creditors"
    response = client.get(endpoint)
    assert response.json() == json.loads(override_json)

    # The other candidate in the ambiguous group must remain unaffected.
    # Explicit Accept: application/json — debitors now has XML/JSON content
    # negotiation (epic `datev-mock-real-data-reconciliation`, W2) and
    # defaults to XML when the Accept header doesn't explicitly request JSON.
    debitors_response = client.get(
        "/datev/api/accounting/v1/clients/c1/fiscal-years/f1/debitors",
        headers={"Accept": "application/json"},
    )
    assert debitors_response.json() != json.loads(override_json)

    _disable(client, "accounting.creditors")

    # Explicit Accept: application/json — with the override disabled, this
    # now falls through to the real content negotiation (creditors also has
    # XML/JSON negotiation as of W2), which defaults to XML.
    response = client.get(endpoint, headers={"Accept": "application/json"})
    assert response.json() != json.loads(override_json)


def test_accounting_accounts_payable_ambiguous_group_resolved_and_served(client):
    # Fingerprint fields updated (W3, epic `datev-mock-real-data-
    # reconciliation`): `open_balance_of_item`/`is_condensed` replace
    # `amount_debit`/`amount_credit` in the ambiguous-group fingerprint —
    # see `app/overrides.py` for why.
    override_json = json.dumps(
        [
            {
                "amount_debit": 123.45,
                "amount_credit": 0.0,
                "open_balance_of_item": 123.45,
                "is_condensed": False,
                "evidence_type": "invoice",
                "debit_credit_identifier": "debit",
            }
        ]
    )

    upload = _upload(
        client, "open_item.json", override_json.encode("utf-8"), "application/json"
    )
    assert upload["status"] == "ambiguous"
    assert set(upload["candidates"]) == {
        "accounting.accounts_payable",
        "accounting.accounts_payable_condense",
        "accounting.accounts_receivable_condense",
    }

    resolve = client.post(
        RESOLVE_ENDPOINT,
        json={"pending_id": upload["pending_id"], "endpoint": "accounting.accounts_payable"},
    )
    assert resolve.status_code == 200

    endpoint = "/datev/api/accounting/v1/clients/c1/fiscal-years/f1/accounts-payable"
    response = client.get(endpoint)
    assert response.json() == json.loads(override_json)

    _disable(client, "accounting.accounts_payable")

    # accounts_payable also gained XML/JSON content negotiation in W3;
    # ambiguous/missing Accept now defaults to XML, same as every other
    # negotiated endpoint (matching W2's precedent fix for creditors/
    # debitors bare GETs in `test_overrides_integration.py`).
    response = client.get(endpoint, headers={"Accept": "application/json"})
    assert response.json() != json.loads(override_json)


def test_accounting_posting_proposal_rules_incoming_ambiguous_group_resolved_and_served(client):
    override_json = json.dumps(
        [
            {
                "assignment_criteria": "custom",
                "posting_proposal_information": "custom info",
                "uncertain_label": "custom label",
            }
        ]
    )

    upload = _upload(
        client, "posting_rule.json", override_json.encode("utf-8"), "application/json"
    )
    assert upload["status"] == "ambiguous"
    assert set(upload["candidates"]) == {
        "accounting.posting_proposal_rules_incoming",
        "accounting.posting_proposal_rules_outgoing",
    }

    resolve = client.post(
        RESOLVE_ENDPOINT,
        json={
            "pending_id": upload["pending_id"],
            "endpoint": "accounting.posting_proposal_rules_incoming",
        },
    )
    assert resolve.status_code == 200

    endpoint = (
        "/datev/api/accounting/v1/clients/c1/fiscal-years/f1/"
        "posting-proposal-rules-incoming-invoices"
    )
    response = client.get(endpoint)
    assert response.json() == json.loads(override_json)

    _disable(client, "accounting.posting_proposal_rules_incoming")

    response = client.get(endpoint)
    assert response.json() != json.loads(override_json)


# --- dms.domains (JSON) ---


def test_dms_domains_serves_active_override_and_falls_back_when_disabled(client):
    override_json = json.dumps([{"name": "Custom Root", "type": "domain"}])

    result = _upload(client, "domains.json", override_json.encode("utf-8"), "application/json")
    assert result == {"status": "matched", "endpoint": "dms.domains"}

    response = client.get("/datev/api/dms/v1/domains")
    assert response.json() == json.loads(override_json)

    _disable(client, "dms.domains")

    response = client.get("/datev/api/dms/v1/domains")
    assert response.json() != json.loads(override_json)
