"""GET /datev/api/accounting/v1/clients — accounting mock endpoint.

Content-negotiated on a single port (58452), with three explicit states:
  - `Accept` explicitly contains `application/json` (and not
    `application/xml`) -> JSON, always.
  - `Accept` explicitly contains `application/xml` (and not
    `application/json`) -> XML, always.
  - Anything else (missing header, `*/*`, unrecognized, or contains both) ->
    ambiguous, so the live `default_accounting_format` setting (read fresh
    from `app.config` on every request) decides.
See "## Decisions" in `odd/tasks/datev-mock.md` for the original XML/JSON
shape rationale, and `odd/tasks/datev-mock-settings.md` for the live-setting
addition.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Request, Response

from app import config, data_store, overrides
from app.json_serializers import serialize_clients_json
from app.xml_serializers import serialize_clients

router = APIRouter(tags=["accounting"])

ENDPOINT = "/datev/api/accounting/v1/clients"

# --- Accounting extension, Phase B batch B1 (extended-endpoints epic) ---
#
# Path templates use FastAPI's own snake_case `{name}` syntax (matching
# Phase A's `master_data.py` precedent), not the compiled spec doc's
# hyphenated `{client-id}` spelling. Per the epic's cross-phase decision,
# none of these filter by their path params — every call returns the same
# fixed fake dataset regardless of the ids in the URL (locked in by the
# `*_ignores_*_id_values` RED tests).

_FISCAL_YEAR_PREFIX = "/datev/api/accounting/v1/clients/{client_id}/fiscal-years/{fiscal_year_id}"

FISCAL_YEARS_ENDPOINT = "/datev/api/accounting/v1/clients/{client_id}/fiscal-years"
COST_SYSTEMS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/cost-systems"
COST_CENTERS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/cost-systems/{{cost_system_id}}/cost-centers"
CREDITORS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/creditors"
DEBITORS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/debitors"
GENERAL_LEDGER_ACCOUNTS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/general-ledger-accounts"

# --- Accounting extension, Phase B batch B2 (extended-endpoints epic) ---
#
# Same conventions as batch B1's constants/handlers above (snake_case path
# params, no path-param filtering).

ACCOUNTS_PAYABLE_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounts-payable"
ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounts-payable/condense"
ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounts-receivable/condense"
ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounting-sequences-processed"
ACCOUNTING_TRANSACTION_KEYS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounting-transaction-keys"
ASSETS_STOCKTAKINGS_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/assets/stocktakings"
POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/posting-proposal-rules-incoming-invoices"
)
POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/posting-proposal-rules-outgoing-invoices"
)
TERMS_OF_PAYMENT_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/terms-of-payment"


def _strip_none(value: Any) -> Any:
    """Recursively drop `None`-valued keys/entries, matching the spec's
    convention of expressing "not set" as field absence (neither spec uses
    OpenAPI `nullable` anywhere)."""
    if isinstance(value, dict):
        return {key: _strip_none(val) for key, val in value.items() if val is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    return value


def _to_json(record: Any) -> dict[str, Any]:
    return _strip_none(asdict(record))


@router.get(
    ENDPOINT,
    summary="List accounting clients",
    description=(
        "Returns ArrayOfClient XML by default (DATEV Irw.Connect.Accounting "
        "contract), or the documented JSON shape when Accept: application/json "
        "is sent. When the Accept header doesn't unambiguously request one "
        "format or the other, the live default_accounting_format setting decides."
    ),
)
def get_accounting_clients(request: Request) -> Response:
    override = overrides.get_active_override("accounting.clients")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    accept = request.headers.get("accept", "").lower()
    wants_json = "application/json" in accept
    wants_xml = "application/xml" in accept

    if wants_json and not wants_xml:
        response_format = "json"
    elif wants_xml and not wants_json:
        response_format = "xml"
    else:
        response_format = config.load_settings().default_accounting_format

    records = data_store.list_accounting_clients()

    if response_format == "json":
        payload = serialize_clients_json(records)
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_clients(records), media_type="application/xml")


@router.get(
    FISCAL_YEARS_ENDPOINT,
    summary="List a client's fiscal years",
    description="Bare JSON array of fiscal-year. Ignores client_id (no path-param filtering, per the epic's cross-phase decision).",
)
def get_fiscal_years(client_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.fiscal_years")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_fiscal_years()]


@router.get(
    COST_SYSTEMS_ENDPOINT,
    summary="List a fiscal year's cost systems",
    description="Bare JSON array of cost-system. Ignores client_id/fiscal_year_id.",
)
def get_cost_systems(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.cost_systems")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_cost_systems()]


@router.get(
    COST_CENTERS_ENDPOINT,
    summary="List a cost system's cost centers",
    description="Bare JSON array of cost-center. Ignores client_id/fiscal_year_id/cost_system_id.",
)
def get_cost_centers(
    client_id: str, fiscal_year_id: str, cost_system_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.cost_centers")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_cost_centers()]


@router.get(
    CREDITORS_ENDPOINT,
    summary="List a fiscal year's creditors",
    description="Bare JSON array of creditor. Ignores client_id/fiscal_year_id.",
)
def get_creditors(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.creditors")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_creditors()]


@router.get(
    DEBITORS_ENDPOINT,
    summary="List a fiscal year's debitors",
    description="Bare JSON array of debitor. Ignores client_id/fiscal_year_id.",
)
def get_debitors(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.debitors")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_debitors()]


@router.get(
    GENERAL_LEDGER_ACCOUNTS_ENDPOINT,
    summary="List a fiscal year's general ledger accounts",
    description="Bare JSON array of general-ledger-account. Ignores client_id/fiscal_year_id.",
)
def get_general_ledger_accounts(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.general_ledger_accounts")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_general_ledger_accounts()]


@router.get(
    ACCOUNTS_PAYABLE_ENDPOINT,
    summary="List a fiscal year's accounts payable open items",
    description="Bare JSON array of open-item. Ignores client_id/fiscal_year_id.",
)
def get_accounts_payable(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.accounts_payable")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_accounts_payable()]


@router.get(
    ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT,
    summary="List a fiscal year's condensed accounts payable open items",
    description=(
        "Bare JSON array of open-item, same schema as accounts-payable (condense "
        "is a server-side aggregation, not a different shape). Ignores "
        "client_id/fiscal_year_id."
    ),
)
def get_accounts_payable_condense(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.accounts_payable_condense")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_accounts_payable_condense()]


@router.get(
    ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT,
    summary="List a fiscal year's condensed accounts receivable open items",
    description="Bare JSON array of open-item, plus receivable-only dunning fields. Ignores client_id/fiscal_year_id.",
)
def get_accounts_receivable_condense(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.accounts_receivable_condense")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_accounts_receivable_condense()]


@router.get(
    ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT,
    summary="List a fiscal year's processed accounting sequences",
    description="Bare JSON array of accounting-sequence-read. Ignores client_id/fiscal_year_id.",
)
def get_accounting_sequences_processed(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.accounting_sequences_processed")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_accounting_sequences_processed()]


@router.get(
    ACCOUNTING_TRANSACTION_KEYS_ENDPOINT,
    summary="List a fiscal year's accounting transaction keys",
    description="Bare JSON array of accounting-transaction-key. Ignores client_id/fiscal_year_id.",
)
def get_accounting_transaction_keys(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.accounting_transaction_keys")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_accounting_transaction_keys()]


@router.get(
    ASSETS_STOCKTAKINGS_ENDPOINT,
    summary="List a fiscal year's asset stocktaking records",
    description="Bare JSON array of stocktaking-record. Ignores client_id/fiscal_year_id.",
)
def get_assets_stocktakings(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.assets_stocktakings")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_assets_stocktakings()]


@router.get(
    POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT,
    summary="List a fiscal year's posting proposal rules for incoming invoices",
    description="Bare JSON array of posting-proposal-rule-incoming-invoices. Ignores client_id/fiscal_year_id.",
)
def get_posting_proposal_rules_incoming_invoices(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.posting_proposal_rules_incoming")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [
        _to_json(record) for record in data_store.list_posting_proposal_rules_incoming_invoices()
    ]


@router.get(
    POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT,
    summary="List a fiscal year's posting proposal rules for outgoing invoices",
    description="Bare JSON array of posting-proposal-rule-outgoing-invoices. Ignores client_id/fiscal_year_id.",
)
def get_posting_proposal_rules_outgoing_invoices(
    client_id: str, fiscal_year_id: str
) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.posting_proposal_rules_outgoing")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [
        _to_json(record) for record in data_store.list_posting_proposal_rules_outgoing_invoices()
    ]


@router.get(
    TERMS_OF_PAYMENT_ENDPOINT,
    summary="List a fiscal year's terms of payment",
    description="Bare JSON array of term-of-payment. Ignores client_id/fiscal_year_id.",
)
def get_terms_of_payment(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    override = overrides.get_active_override("accounting.terms_of_payment")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_terms_of_payment()]
