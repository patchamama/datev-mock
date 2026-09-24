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
import uuid
from dataclasses import asdict
from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException, Request, Response

from app import config, data_store, db, overrides, scoped_data
from app.json_serializers import serialize_clients_json
from app.models import (
    AccountingTransactionKey,
    Addressee,
    AssetStocktaking,
    CostAccountingRecord,
    CostCenter,
    CostCenterProperty,
    CostSequence,
    Creditor,
    Debitor,
    GeneralLedgerAccount,
    TermOfPayment,
    VariousAddress,
)
from app.write_models import (
    AccountingSequenceCreateWrite,
    AssetStocktakingWrite,
    CashRegisterPostingWrite,
    CostAccountingRecordWrite,
    CostCenterPropertyWrite,
    CostCenterWrite,
    CostSequenceWrite,
    CreditorWrite,
    DebitorWrite,
    IncomingInvoicePostingWrite,
    InternalCostServiceWrite,
    OutgoingInvoicePostingWrite,
    TermOfPaymentWrite,
    VariousAddressWrite,
)
from app.xml_serializers import (
    serialize_accounting_sequences_processed,
    serialize_accounting_transaction_keys,
    serialize_assets_stocktakings,
    serialize_clients,
    serialize_cost_centers,
    serialize_cost_systems,
    serialize_creditors,
    serialize_debitors,
    serialize_fiscal_years,
    serialize_general_ledger_accounts,
    serialize_open_items,
    serialize_posting_proposal_rules,
    serialize_terms_of_payment,
)

router = APIRouter(tags=["accounting"])

# --- P2 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group A") -- see the module-bottom "write endpoints" section for the
# routes themselves. `Creditor`/`Debitor`'s nested object fields
# (`natural_person`/`legal_person`/`not_specified_person`/`addresses`/
# `banks`/`communications`/`accounting_information`) have no dedicated XML
# sub-rendering (real evidence: never populated in the default, non-expand
# response either -- see `Creditor`'s own docstring), so a raw dict a caller
# POSTed would otherwise render as a broken Python `repr()` string inside
# XML. They're nilled for the merged GET view; full fidelity of whatever
# was actually written stays visible in the admin UI's "Stored records"
# card and in the raw JSON `data_json` any caller wrote.
_BUSINESS_PARTNER_NIL_FIELDS = frozenset(
    {
        "natural_person",
        "legal_person",
        "not_specified_person",
        "addresses",
        "banks",
        "communications",
        "accounting_information",
    }
)

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

# --- P2 write-endpoint-only path constants ---
#
# `ASSET_STOCKTAKING_ENDPOINT` is deliberately a *different* URL shape than
# `ASSETS_STOCKTAKINGS_ENDPOINT` above (`assets/stocktakings`, the existing
# read-only list) -- the write side's spec path is
# `assets/{asset-id}/stocktaking/` (singular, by-id), a distinct real
# endpoint, not an alternate spelling of the list one. Per the task's own
# note about the spec's trailing slash: no trailing slash here, for
# consistency with every other path constant in this module (FastAPI
# doesn't require one, and Starlette would otherwise 307-redirect a
# no-slash request to it).
ASSET_STOCKTAKING_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/assets/{{asset_id}}/stocktaking"

# --- P3 write-endpoint path constants (Group B, no prior GET modeling) ---
#
# Same `_FISCAL_YEAR_PREFIX`/snake_case-path-param/no-path-filtering
# conventions as every constant above. `COST_CENTER_PROPERTIES_ENDPOINT`/
# `COST_SEQUENCES_ENDPOINT`/`INTERNAL_COST_SERVICES_ENDPOINT` nest under the
# same `cost-systems/{cost_system_id}` segment as `COST_CENTERS_ENDPOINT`.
COST_CENTER_PROPERTIES_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/cost-systems/{{cost_system_id}}/cost-center-properties"
)
COST_SEQUENCES_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/cost-systems/{{cost_system_id}}/cost-sequences"
INTERNAL_COST_SERVICES_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/cost-systems/{{cost_system_id}}/internal-cost-services"
)
VARIOUS_ADDRESSES_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/various-addresses"
# Deliberately distinct from ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT above --
# that's the existing read-only "processed" view; this is the create-only
# write operation the spec documents separately (Appendix A, Group B).
ACCOUNTING_SEQUENCES_ENDPOINT = f"{_FISCAL_YEAR_PREFIX}/accounting-sequences"
POSTING_PROPOSALS_INCOMING_INVOICES_BATCH_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/posting-proposals-incoming-invoices/batch"
)
POSTING_PROPOSALS_OUTGOING_INVOICES_BATCH_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/posting-proposals-outgoing-invoices/batch"
)
POSTING_PROPOSALS_CASH_REGISTER_BATCH_ENDPOINT = (
    f"{_FISCAL_YEAR_PREFIX}/posting-proposals-cash-register/batch"
)


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


# --- Real-data reconciliation epic, W2 batch A ---
#
# XML/JSON content negotiation for `fiscal_years`, `cost_systems`,
# `cost_centers`, `creditors`, `debitors`, `general_ledger_accounts` — the
# exact same mechanism `get_accounting_clients` above already implements
# (`Accept: application/json` explicit -> JSON; `Accept: application/xml`
# explicit or ambiguous/missing -> the live `default_accounting_format`
# setting, which defaults to `"xml"`). Factored into a shared helper here
# since 6 endpoints now need it (accounting.clients' own inline copy above
# is intentionally left untouched — out of this batch's scope).


def _negotiate_format(request: Request) -> str:
    accept = request.headers.get("accept", "").lower()
    wants_json = "application/json" in accept
    wants_xml = "application/xml" in accept

    if wants_json and not wants_xml:
        return "json"
    if wants_xml and not wants_json:
        return "xml"
    return config.load_settings().default_accounting_format


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
    description=(
        "Returns ArrayOfFiscalYear XML by default, or a bare JSON array when "
        "Accept: application/json is sent (same content negotiation as "
        "accounting.clients). Deterministically scoped by client_id — see "
        "app/scoped_data.py."
    ),
)
def get_fiscal_years(client_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.fiscal_years")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_fiscal_years_for_client(client_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_fiscal_years(records), media_type="application/xml")


@router.get(
    COST_SYSTEMS_ENDPOINT,
    summary="List a fiscal year's cost systems",
    description=(
        "Returns ArrayOfCostSystems XML by default (confirmed real shape), "
        "or a bare JSON array when Accept: application/json is sent. "
        "Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_cost_systems(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.cost_systems")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_cost_systems_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_cost_systems(records), media_type="application/xml")


@router.get(
    COST_CENTERS_ENDPOINT,
    summary="List a cost system's cost centers",
    description=(
        "Returns ArrayOfCostCenter XML by default (inferred by pattern - no "
        "direct real XML evidence for this endpoint), or a bare JSON array "
        "when Accept: application/json is sent. Deterministically scoped by "
        "client_id/fiscal_year_id/cost_system_id — see app/scoped_data.py."
    ),
)
def get_cost_centers(
    client_id: str, fiscal_year_id: str, cost_system_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.cost_centers")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = db.merge_with_stored(
        scoped_data.get_cost_centers_for_scope(client_id, fiscal_year_id, cost_system_id),
        "accounting.cost_centers",
        CostCenter,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_cost_centers(records), media_type="application/xml")


@router.get(
    CREDITORS_ENDPOINT,
    summary="List a fiscal year's creditors",
    description=(
        "Returns ArrayOfCreditor XML by default (inferred by pattern from "
        "debitors' confirmed real XML - same BusinessPartners contract "
        "family), or a bare JSON array when Accept: application/json is "
        "sent. Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_creditors(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.creditors")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = db.merge_with_stored(
        scoped_data.get_creditors_for_scope(client_id, fiscal_year_id),
        "accounting.creditors",
        Creditor,
        nil_fields=_BUSINESS_PARTNER_NIL_FIELDS,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_creditors(records), media_type="application/xml")


@router.get(
    DEBITORS_ENDPOINT,
    summary="List a fiscal year's debitors",
    description=(
        "Returns ArrayOfDebitor XML by default (confirmed real shape), or a "
        "bare JSON array when Accept: application/json is sent. "
        "Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_debitors(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.debitors")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = db.merge_with_stored(
        scoped_data.get_debitors_for_scope(client_id, fiscal_year_id),
        "accounting.debitors",
        Debitor,
        nil_fields=_BUSINESS_PARTNER_NIL_FIELDS,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_debitors(records), media_type="application/xml")


@router.get(
    GENERAL_LEDGER_ACCOUNTS_ENDPOINT,
    summary="List a fiscal year's general ledger accounts",
    description=(
        "Returns ArrayOfGeneralLedgerAccount XML by default (inferred by "
        "pattern - no direct real XML evidence for this endpoint), or a "
        "bare JSON array when Accept: application/json is sent. "
        "Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_general_ledger_accounts(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.general_ledger_accounts")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_general_ledger_accounts_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(
        content=serialize_general_ledger_accounts(records), media_type="application/xml"
    )


@router.get(
    ACCOUNTS_PAYABLE_ENDPOINT,
    summary="List a fiscal year's accounts payable open items",
    description=(
        "Returns ArrayOfOpenItem XML by default (inferred by pattern - no "
        "direct real XML evidence for this endpoint), or a bare JSON array "
        "when Accept: application/json is sent. Deterministically scoped by "
        "client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_accounts_payable(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.accounts_payable")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_accounts_payable_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_open_items(records), media_type="application/xml")


@router.get(
    ACCOUNTS_PAYABLE_CONDENSE_ENDPOINT,
    summary="List a fiscal year's condensed accounts payable open items",
    description=(
        "Same schema/negotiation as accounts-payable (condense is a "
        "server-side aggregation, not a different shape). Deterministically "
        "scoped by client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_accounts_payable_condense(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.accounts_payable_condense")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_accounts_payable_condense_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_open_items(records), media_type="application/xml")


@router.get(
    ACCOUNTS_RECEIVABLE_CONDENSE_ENDPOINT,
    summary="List a fiscal year's condensed accounts receivable open items",
    description=(
        "Same OpenItem schema/negotiation as accounts-payable, plus the "
        "receivable-only dunning_date1/2/3 fields. Deterministically scoped "
        "by client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_accounts_receivable_condense(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.accounts_receivable_condense")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_accounts_receivable_condense_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_open_items(records), media_type="application/xml")


@router.get(
    ACCOUNTING_SEQUENCES_PROCESSED_ENDPOINT,
    summary="List a fiscal year's processed accounting sequences",
    description=(
        "Returns ArrayOfAccountingSequenceProcessed XML by default "
        "(inferred by pattern - no direct real XML evidence for this "
        "endpoint), or a bare JSON array when Accept: application/json is "
        "sent. Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_accounting_sequences_processed(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.accounting_sequences_processed")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_accounting_sequences_processed_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(
        content=serialize_accounting_sequences_processed(records), media_type="application/xml"
    )


@router.get(
    ACCOUNTING_TRANSACTION_KEYS_ENDPOINT,
    summary="List a fiscal year's accounting transaction keys",
    description=(
        "Returns ArrayOfAccountingTransactionKey XML by default (inferred "
        "by pattern - no direct real XML evidence for this endpoint), or a "
        "bare JSON array when Accept: application/json is sent. "
        "Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_accounting_transaction_keys(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.accounting_transaction_keys")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_accounting_transaction_keys_for_scope(client_id, fiscal_year_id)
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(
        content=serialize_accounting_transaction_keys(records), media_type="application/xml"
    )


@router.get(
    ASSETS_STOCKTAKINGS_ENDPOINT,
    summary="List a fiscal year's asset stocktaking records",
    description=(
        "Returns ArrayOfAssetStocktaking XML by default (inferred by "
        "pattern - no real capture exists for this endpoint at all), or a "
        "bare JSON array when Accept: application/json is sent. "
        "Deterministically scoped by client_id/fiscal_year_id — see "
        "app/scoped_data.py."
    ),
)
def get_assets_stocktakings(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.assets_stocktakings")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = db.merge_with_stored(
        scoped_data.get_assets_stocktakings_for_scope(client_id, fiscal_year_id),
        "accounting.assets_stocktakings",
        AssetStocktaking,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_assets_stocktakings(records), media_type="application/xml")


@router.get(
    POSTING_PROPOSAL_RULES_INCOMING_INVOICES_ENDPOINT,
    summary="List a fiscal year's posting proposal rules for incoming invoices",
    description=(
        "Returns ArrayOfPostingProposalRule XML by default (inferred by "
        "pattern - both real captures returned empty [] arrays, no field-"
        "shape evidence beyond endpoint existence), or a bare JSON array "
        "when Accept: application/json is sent. Deterministically scoped by "
        "client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_posting_proposal_rules_incoming_invoices(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.posting_proposal_rules_incoming")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_posting_proposal_rules_incoming_invoices_for_scope(
        client_id, fiscal_year_id
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_posting_proposal_rules(records), media_type="application/xml")


@router.get(
    POSTING_PROPOSAL_RULES_OUTGOING_INVOICES_ENDPOINT,
    summary="List a fiscal year's posting proposal rules for outgoing invoices",
    description=(
        "Returns ArrayOfPostingProposalRule XML by default (inferred by "
        "pattern - both real captures returned empty [] arrays, no field-"
        "shape evidence beyond endpoint existence; shares the same "
        "PostingProposalRule contract as the incoming variant), or a bare "
        "JSON array when Accept: application/json is sent. Deterministically "
        "scoped by client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_posting_proposal_rules_outgoing_invoices(
    client_id: str, fiscal_year_id: str, request: Request
) -> Response:
    override = overrides.get_active_override("accounting.posting_proposal_rules_outgoing")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = scoped_data.get_posting_proposal_rules_outgoing_invoices_for_scope(
        client_id, fiscal_year_id
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_posting_proposal_rules(records), media_type="application/xml")


@router.get(
    TERMS_OF_PAYMENT_ENDPOINT,
    summary="List a fiscal year's terms of payment",
    description=(
        "Returns ArrayOfTermOfPayment XML by default (inferred by pattern - "
        "no direct real XML evidence for this endpoint), or a bare JSON "
        "array when Accept: application/json is sent. Deterministically "
        "scoped by client_id/fiscal_year_id — see app/scoped_data.py."
    ),
)
def get_terms_of_payment(client_id: str, fiscal_year_id: str, request: Request) -> Response:
    override = overrides.get_active_override("accounting.terms_of_payment")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = db.merge_with_stored(
        scoped_data.get_terms_of_payment_for_scope(client_id, fiscal_year_id),
        "accounting.terms_of_payment",
        TermOfPayment,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    if _negotiate_format(request) == "json":
        payload = [_to_json(record) for record in records]
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_terms_of_payment(records), media_type="application/xml")


# --- P3 GET endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group B") ---
#
# These 4 resources are brand new to this mock -- no fake dataset exists for
# any of them (architecture decision #5's "no fake_data.py generator" call),
# so unlike every Group A GET handler above there's nothing to merge with:
# each handler lists straight from `app.db`, converts each stored row back
# to its dataclass via `db.record_to_dataclass`, and serializes to JSON.
# JSON-only (no XML) per the feature doc's explicit instruction for
# genuinely new Group B resources -- no real capture evidence exists to
# justify inventing an XML shape, and none of the accompanying write models
# are validated against any XML contract either.


@router.get(
    COST_CENTER_PROPERTIES_ENDPOINT,
    summary="List a cost system's cost-center properties",
    description=(
        "New in P3 (Group B) -- JSON-only bare array (no fake dataset "
        "exists for this new resource; returns whatever's been PUT so "
        "far). Filtered by client_id/fiscal_year_id (architecture decision "
        "#5's db.py scope-forwarding fix); cost_system_id is still ignored "
        "-- the generic stored_records table has no cost_system_id column."
    ),
)
def get_cost_center_properties(
    client_id: str, fiscal_year_id: str, cost_system_id: str
) -> list[dict[str, Any]]:
    records = [
        db.record_to_dataclass(CostCenterProperty, row)
        for row in db.list_records(
            "accounting.cost_center_properties", client_id=client_id, fiscal_year_id=fiscal_year_id
        )
    ]
    return [_to_json(record) for record in records]


@router.get(
    COST_SEQUENCES_ENDPOINT,
    summary="List a cost system's cost sequences",
    description=(
        "New in P3 (Group B) -- JSON-only bare array, no fake dataset. "
        "Filtered by client_id/fiscal_year_id; cost_system_id is still "
        "ignored -- the generic stored_records table has no "
        "cost_system_id column."
    ),
)
def get_cost_sequences(
    client_id: str, fiscal_year_id: str, cost_system_id: str
) -> list[dict[str, Any]]:
    records = [
        db.record_to_dataclass(CostSequence, row)
        for row in db.list_records(
            "accounting.cost_sequences", client_id=client_id, fiscal_year_id=fiscal_year_id
        )
    ]
    return [_to_json(record) for record in records]


@router.get(
    COST_SEQUENCES_ENDPOINT + "/{cost_sequence_id}/cost-accounting-records",
    summary="List a cost sequence's cost accounting records",
    description=(
        "New in P3 (Group B) -- JSON-only bare array, no fake dataset. "
        "Filtered by client_id/fiscal_year_id; cost_system_id/"
        "cost_sequence_id are still ignored -- the generic stored_records "
        "table has no columns for them."
    ),
)
def get_cost_accounting_records(
    client_id: str, fiscal_year_id: str, cost_system_id: str, cost_sequence_id: str
) -> list[dict[str, Any]]:
    records = [
        db.record_to_dataclass(CostAccountingRecord, row)
        for row in db.list_records(
            "accounting.cost_accounting_records", client_id=client_id, fiscal_year_id=fiscal_year_id
        )
    ]
    return [_to_json(record) for record in records]


@router.get(
    VARIOUS_ADDRESSES_ENDPOINT,
    summary="List a fiscal year's various addresses",
    description=(
        "New in P3 (Group B) -- JSON-only bare array, no fake dataset. "
        "Filtered by client_id/fiscal_year_id (architecture decision #5's "
        "db.py scope-forwarding fix)."
    ),
)
def get_various_addresses(client_id: str, fiscal_year_id: str) -> list[dict[str, Any]]:
    records = [
        db.record_to_dataclass(VariousAddress, row)
        for row in db.list_records(
            "accounting.various_addresses", client_id=client_id, fiscal_year_id=fiscal_year_id
        )
    ]
    return [_to_json(record) for record in records]


# --- P2 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group A") ---
#
# Every write endpoint: validate the Pydantic body (FastAPI does this
# automatically), generate an `id` (uuid4) if the caller didn't supply one
# (or use the URL's own `{..._id}` path param for a by-id PUT), persist via
# `app.db.upsert_record`, and echo the stored record back as JSON -- this
# mock's existing convention (see `app/routers/admin.py`'s master-data/
# accounting CRUD, which already does exactly this). `201` for creates,
# `200` for updates, matching ordinary REST/FastAPI convention.


def _write_record(
    resource_type: str,
    body: Any,
    record_id: Optional[str] = None,
    client_id: Optional[str] = None,
    fiscal_year_id: Optional[str] = None,
) -> dict[str, Any]:
    data = body.model_dump(exclude_none=True)
    resolved_id = record_id or data.get("id") or str(uuid.uuid4())
    data["id"] = resolved_id
    return db.upsert_record(
        resource_type, resolved_id, data, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


# --- P2 write-side FK validation (architecture decision #6 + the feature
# doc's Appendix table) ---
#
# One shared `_validate_reference` raises the chosen 422 status (decision
# #6) when a write-body field references an id/number that doesn't exist in
# either this request's scope's generated dataset (`app.scoped_data`) or
# whatever's already been written via SQLite for that same scope --
# exactly what a subsequent GET in the same scope would show. Every
# "candidate set" builder below reuses `db.merge_with_stored` (the same
# union logic every Group A GET route above already uses) instead of
# querying SQLite directly, per the doc's explicit "don't reinvent it"
# instruction. `None`/omitted values are always left unvalidated -- every
# FK-shaped field below is `Optional` except `InternalCostServiceWrite
# .cost_center_from`/`cost_center_to` and `CashRegisterPostingWrite
# .cash_account_number`, which are already non-`None` by Pydantic's own
# required-field enforcement before any handler body runs.


def _validate_reference(value: Optional[Any], candidates: set, field_name: str) -> None:
    if value is not None and value not in candidates:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: no matching record found for {value!r} in this scope",
        )


def _as_int(value: Any) -> Optional[int]:
    """Best-effort int coercion for a candidate set whose dataclass field is
    typed `str` (e.g. `TermOfPayment.id`) but the write-body field
    referencing it is typed `int` (e.g. `term_of_payment_id`) -- a stored
    record whose id isn't int-parseable (e.g. a caller-supplied UUID)
    simply never matches an int-typed reference, same as a real API
    wouldn't match it either."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_candidates(records: list[Any], attr: str) -> set[int]:
    coerced = (_as_int(getattr(record, attr)) for record in records)
    return {value for value in coerced if value is not None}


def _merged_creditors(client_id: str, fiscal_year_id: str) -> list[Creditor]:
    return db.merge_with_stored(
        scoped_data.get_creditors_for_scope(client_id, fiscal_year_id),
        "accounting.creditors",
        Creditor,
        nil_fields=_BUSINESS_PARTNER_NIL_FIELDS,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


def _merged_debitors(client_id: str, fiscal_year_id: str) -> list[Debitor]:
    return db.merge_with_stored(
        scoped_data.get_debitors_for_scope(client_id, fiscal_year_id),
        "accounting.debitors",
        Debitor,
        nil_fields=_BUSINESS_PARTNER_NIL_FIELDS,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


def _merged_terms_of_payment(client_id: str, fiscal_year_id: str) -> list[TermOfPayment]:
    return db.merge_with_stored(
        scoped_data.get_terms_of_payment_for_scope(client_id, fiscal_year_id),
        "accounting.terms_of_payment",
        TermOfPayment,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


def _merged_general_ledger_accounts(
    client_id: str, fiscal_year_id: str
) -> list[GeneralLedgerAccount]:
    return db.merge_with_stored(
        scoped_data.get_general_ledger_accounts_for_scope(client_id, fiscal_year_id),
        "accounting.general_ledger_accounts",
        GeneralLedgerAccount,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


def _merged_accounting_transaction_keys(
    client_id: str, fiscal_year_id: str
) -> list[AccountingTransactionKey]:
    return db.merge_with_stored(
        scoped_data.get_accounting_transaction_keys_for_scope(client_id, fiscal_year_id),
        "accounting.accounting_transaction_keys",
        AccountingTransactionKey,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


def _primary_cost_center_ids(client_id: str, fiscal_year_id: str) -> set[str]:
    """Same "fiscal year's primary cost system" convention architecture
    decision #4 established for `OpenItem.kost1_cost_center_id` in P1 --
    every write-side field below validating against `CostCenter.id` with no
    `cost_system_id` of its own in its path reuses it here."""
    cost_systems = scoped_data.get_cost_systems_for_scope(client_id, fiscal_year_id)
    primary_cost_system_id = cost_systems[0].id
    merged = db.merge_with_stored(
        scoped_data.get_cost_centers_for_scope(client_id, fiscal_year_id, primary_cost_system_id),
        "accounting.cost_centers",
        CostCenter,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )
    return {record.id for record in merged}


def _validate_business_partner_write(
    body: Union[CreditorWrite, DebitorWrite], client_id: str, fiscal_year_id: str
) -> None:
    addressee_ids = {
        record.id
        for record in db.merge_with_stored(
            data_store.list_addressees(), "master_data.addressees", Addressee
        )
    }
    _validate_reference(body.addressee_id, addressee_ids, "addressee_id")
    # business_partner_relation_id: no modeled target resource (decision #4/#6) -- left unvalidated.
    if body.accounting_information is not None:
        term_of_payment_ids = _int_candidates(
            _merged_terms_of_payment(client_id, fiscal_year_id), "id"
        )
        _validate_reference(
            body.accounting_information.term_of_payment_id,
            term_of_payment_ids,
            "accounting_information.term_of_payment_id",
        )


@router.post(DEBITORS_ENDPOINT, status_code=201, summary="Create a debitor")
def post_debitor(client_id: str, fiscal_year_id: str, body: DebitorWrite) -> dict[str, Any]:
    _validate_business_partner_write(body, client_id, fiscal_year_id)
    return _write_record(
        "accounting.debitors", body, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


@router.put(
    DEBITORS_ENDPOINT,
    summary="Bulk-update debitors",
    description=(
        "Body is a JSON array (the real spec's Content-Type is "
        "application/merge-patch+json; FastAPI parses the same array body "
        "regardless, no special ASGI handling needed for that content-type "
        "nuance)."
    ),
)
def put_debitors(
    client_id: str, fiscal_year_id: str, body: list[DebitorWrite]
) -> list[dict[str, Any]]:
    for item in body:
        _validate_business_partner_write(item, client_id, fiscal_year_id)
    return [
        _write_record("accounting.debitors", item, client_id=client_id, fiscal_year_id=fiscal_year_id)
        for item in body
    ]


@router.put(DEBITORS_ENDPOINT + "/{debitor_id}", summary="Update a debitor by id")
def put_debitor(
    client_id: str, fiscal_year_id: str, debitor_id: str, body: DebitorWrite
) -> dict[str, Any]:
    _validate_business_partner_write(body, client_id, fiscal_year_id)
    return _write_record(
        "accounting.debitors",
        body,
        record_id=debitor_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.post(CREDITORS_ENDPOINT, status_code=201, summary="Create a creditor")
def post_creditor(client_id: str, fiscal_year_id: str, body: CreditorWrite) -> dict[str, Any]:
    _validate_business_partner_write(body, client_id, fiscal_year_id)
    return _write_record(
        "accounting.creditors", body, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


@router.put(
    CREDITORS_ENDPOINT,
    summary="Bulk-update creditors",
    description=(
        "Body is a JSON array (same application/merge-patch+json note as "
        "debitors' bulk PUT above)."
    ),
)
def put_creditors(
    client_id: str, fiscal_year_id: str, body: list[CreditorWrite]
) -> list[dict[str, Any]]:
    for item in body:
        _validate_business_partner_write(item, client_id, fiscal_year_id)
    return [
        _write_record(
            "accounting.creditors", item, client_id=client_id, fiscal_year_id=fiscal_year_id
        )
        for item in body
    ]


@router.put(CREDITORS_ENDPOINT + "/{creditor_id}", summary="Update a creditor by id")
def put_creditor(
    client_id: str, fiscal_year_id: str, creditor_id: str, body: CreditorWrite
) -> dict[str, Any]:
    _validate_business_partner_write(body, client_id, fiscal_year_id)
    return _write_record(
        "accounting.creditors",
        body,
        record_id=creditor_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.post(TERMS_OF_PAYMENT_ENDPOINT, status_code=201, summary="Create a term of payment")
def post_term_of_payment(
    client_id: str, fiscal_year_id: str, body: TermOfPaymentWrite
) -> dict[str, Any]:
    return _write_record(
        "accounting.terms_of_payment", body, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


@router.put(
    TERMS_OF_PAYMENT_ENDPOINT + "/{term_of_payment_id}", summary="Update a term of payment by id"
)
def put_term_of_payment(
    client_id: str, fiscal_year_id: str, term_of_payment_id: str, body: TermOfPaymentWrite
) -> dict[str, Any]:
    return _write_record(
        "accounting.terms_of_payment",
        body,
        record_id=term_of_payment_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.put(
    ASSET_STOCKTAKING_ENDPOINT,
    summary="Update an asset's stocktaking record",
    description=(
        "The URL's asset_id is used as the stored record's own id (same "
        "by-id convention as every other PUT-by-id endpoint here) -- the "
        "real spec's asset_number/inventory_number are separate required "
        "body fields, not the same thing as this path id."
    ),
)
def put_asset_stocktaking(
    client_id: str, fiscal_year_id: str, asset_id: str, body: AssetStocktakingWrite
) -> dict[str, Any]:
    if body.general_ledger_account is not None:
        gl_account_numbers = _int_candidates(
            _merged_general_ledger_accounts(client_id, fiscal_year_id), "account_number"
        )
        _validate_reference(
            body.general_ledger_account.account_number,
            gl_account_numbers,
            "general_ledger_account.account_number",
        )
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    _validate_reference(body.kost1_cost_center_id, cost_center_ids, "kost1_cost_center_id")
    return _write_record(
        "accounting.assets_stocktakings",
        body,
        record_id=asset_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.put(
    COST_CENTERS_ENDPOINT + "/{cost_center_id}",
    summary="Update a cost center by id",
)
def put_cost_center(
    client_id: str,
    fiscal_year_id: str,
    cost_system_id: str,
    cost_center_id: str,
    body: CostCenterWrite,
) -> dict[str, Any]:
    return _write_record(
        "accounting.cost_centers",
        body,
        record_id=cost_center_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


# --- P3 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group B") ---
#
# Same `_write_record` helper as every P2 Group A endpoint above. 11 of
# these 16 operations have a matching GET handler (added above); the
# remaining 5 (internal-cost-services, accounting-sequences, the 3
# posting-proposals batches) are create-only per the spec (no GET
# documented) -- still persisted via `_write_record`/`app.db` for admin-UI
# visibility/audit (architecture decision #5), just with no public GET
# route the real API doesn't have.


@router.put(
    COST_CENTER_PROPERTIES_ENDPOINT + "/{cost_center_property_id}",
    summary="Update a cost-center property by id",
)
def put_cost_center_property(
    client_id: str,
    fiscal_year_id: str,
    cost_system_id: str,
    cost_center_property_id: str,
    body: CostCenterPropertyWrite,
) -> dict[str, Any]:
    return _write_record(
        "accounting.cost_center_properties",
        body,
        record_id=cost_center_property_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.put(
    COST_SEQUENCES_ENDPOINT + "/{cost_sequence_id}",
    summary="Update a cost sequence by id",
)
def put_cost_sequence(
    client_id: str,
    fiscal_year_id: str,
    cost_system_id: str,
    cost_sequence_id: str,
    body: CostSequenceWrite,
) -> dict[str, Any]:
    return _write_record(
        "accounting.cost_sequences",
        body,
        record_id=cost_sequence_id,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.post(
    COST_SEQUENCES_ENDPOINT + "/{cost_sequence_id}/cost-accounting-records",
    status_code=201,
    summary="Create a cost sequence's cost accounting record",
)
def post_cost_accounting_record(
    client_id: str,
    fiscal_year_id: str,
    cost_system_id: str,
    cost_sequence_id: str,
    body: CostAccountingRecordWrite,
) -> dict[str, Any]:
    gl_account_numbers = _int_candidates(
        _merged_general_ledger_accounts(client_id, fiscal_year_id), "account_number"
    )
    _validate_reference(body.account_number, gl_account_numbers, "account_number")
    _validate_reference(body.contra_account_number, gl_account_numbers, "contra_account_number")
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    _validate_reference(body.alternative_cost_center, cost_center_ids, "alternative_cost_center")
    _validate_reference(body.cost_center, cost_center_ids, "cost_center")
    return _write_record(
        "accounting.cost_accounting_records",
        body,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.post(
    VARIOUS_ADDRESSES_ENDPOINT, status_code=201, summary="Create a various-address record"
)
def post_various_address(
    client_id: str, fiscal_year_id: str, body: VariousAddressWrite
) -> dict[str, Any]:
    creditors = _merged_creditors(client_id, fiscal_year_id)
    debitors = _merged_debitors(client_id, fiscal_year_id)
    account_numbers = {record.account_number for record in creditors} | {
        record.account_number for record in debitors
    }
    _validate_reference(body.account_number, account_numbers, "account_number")
    business_partner_numbers = {record.business_partner_number for record in creditors} | {
        record.business_partner_number for record in debitors
    }
    _validate_reference(
        body.business_partner_number, business_partner_numbers, "business_partner_number"
    )
    return _write_record(
        "accounting.various_addresses", body, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


@router.post(
    INTERNAL_COST_SERVICES_ENDPOINT,
    status_code=201,
    summary="Create an internal cost service",
    description=(
        "Create-only -- no GET documented in the spec (Appendix A). Still "
        "persisted via app.db for admin-UI visibility/audit (architecture "
        "decision #5); only the admin 'Stored records' card surfaces it, "
        "no public GET route."
    ),
)
def post_internal_cost_service(
    client_id: str, fiscal_year_id: str, cost_system_id: str, body: InternalCostServiceWrite
) -> dict[str, Any]:
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    _validate_reference(body.cost_center_from, cost_center_ids, "cost_center_from")
    _validate_reference(body.cost_center_to, cost_center_ids, "cost_center_to")
    return _write_record(
        "accounting.internal_cost_services",
        body,
        client_id=client_id,
        fiscal_year_id=fiscal_year_id,
    )


@router.post(
    ACCOUNTING_SEQUENCES_ENDPOINT,
    status_code=201,
    summary="Create an accounting sequence",
    description=(
        "Create-only -- no GET documented (distinct from the existing "
        "read-only accounting-sequences-processed endpoint above -- see "
        "ACCOUNTING_SEQUENCES_ENDPOINT's own comment). Same admin-only "
        "visibility as internal-cost-services above."
    ),
)
def post_accounting_sequence(
    client_id: str, fiscal_year_id: str, body: AccountingSequenceCreateWrite
) -> dict[str, Any]:
    return _write_record(
        "accounting.accounting_sequences", body, client_id=client_id, fiscal_year_id=fiscal_year_id
    )


@router.post(
    POSTING_PROPOSALS_INCOMING_INVOICES_BATCH_ENDPOINT,
    status_code=201,
    summary="Batch-submit posting proposals for incoming invoices",
    description="Create-only, array body -- no GET documented.",
)
def post_posting_proposals_incoming_invoices_batch(
    client_id: str, fiscal_year_id: str, body: list[IncomingInvoicePostingWrite]
) -> list[dict[str, Any]]:
    transaction_keys = _int_candidates(
        _merged_accounting_transaction_keys(client_id, fiscal_year_id), "number"
    )
    gl_account_numbers = _int_candidates(
        _merged_general_ledger_accounts(client_id, fiscal_year_id), "account_number"
    )
    creditor_account_numbers = _int_candidates(
        _merged_creditors(client_id, fiscal_year_id), "account_number"
    )
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    for item in body:
        _validate_reference(
            item.accounting_transaction_key, transaction_keys, "accounting_transaction_key"
        )
        _validate_reference(item.account_number, gl_account_numbers, "account_number")
        _validate_reference(
            item.creditor_account_number, creditor_account_numbers, "creditor_account_number"
        )
        _validate_reference(item.kost1_cost_center_id, cost_center_ids, "kost1_cost_center_id")
        _validate_reference(item.kost2_cost_center_id, cost_center_ids, "kost2_cost_center_id")
    return [
        _write_record(
            "accounting.posting_proposals_incoming_invoices",
            item,
            client_id=client_id,
            fiscal_year_id=fiscal_year_id,
        )
        for item in body
    ]


@router.post(
    POSTING_PROPOSALS_OUTGOING_INVOICES_BATCH_ENDPOINT,
    status_code=201,
    summary="Batch-submit posting proposals for outgoing invoices",
    description="Create-only, array body -- no GET documented.",
)
def post_posting_proposals_outgoing_invoices_batch(
    client_id: str, fiscal_year_id: str, body: list[OutgoingInvoicePostingWrite]
) -> list[dict[str, Any]]:
    transaction_keys = _int_candidates(
        _merged_accounting_transaction_keys(client_id, fiscal_year_id), "number"
    )
    gl_account_numbers = _int_candidates(
        _merged_general_ledger_accounts(client_id, fiscal_year_id), "account_number"
    )
    debitor_account_numbers = _int_candidates(
        _merged_debitors(client_id, fiscal_year_id), "account_number"
    )
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    for item in body:
        _validate_reference(
            item.accounting_transaction_key, transaction_keys, "accounting_transaction_key"
        )
        _validate_reference(item.account_number, gl_account_numbers, "account_number")
        _validate_reference(
            item.debitor_account_number, debitor_account_numbers, "debitor_account_number"
        )
        _validate_reference(item.kost1_cost_center_id, cost_center_ids, "kost1_cost_center_id")
        _validate_reference(item.kost2_cost_center_id, cost_center_ids, "kost2_cost_center_id")
    return [
        _write_record(
            "accounting.posting_proposals_outgoing_invoices",
            item,
            client_id=client_id,
            fiscal_year_id=fiscal_year_id,
        )
        for item in body
    ]


@router.post(
    POSTING_PROPOSALS_CASH_REGISTER_BATCH_ENDPOINT,
    status_code=201,
    summary="Batch-submit posting proposals for the cash register",
    description="Create-only, array body -- no GET documented.",
)
def post_posting_proposals_cash_register_batch(
    client_id: str, fiscal_year_id: str, body: list[CashRegisterPostingWrite]
) -> list[dict[str, Any]]:
    transaction_keys = _int_candidates(
        _merged_accounting_transaction_keys(client_id, fiscal_year_id), "number"
    )
    gl_account_numbers = _int_candidates(
        _merged_general_ledger_accounts(client_id, fiscal_year_id), "account_number"
    )
    cost_center_ids = _primary_cost_center_ids(client_id, fiscal_year_id)
    for item in body:
        _validate_reference(
            item.accounting_transaction_key, transaction_keys, "accounting_transaction_key"
        )
        _validate_reference(item.cash_account_number, gl_account_numbers, "cash_account_number")
        _validate_reference(
            item.contra_account_number, gl_account_numbers, "contra_account_number"
        )
        _validate_reference(item.kost1_cost_center_id, cost_center_ids, "kost1_cost_center_id")
        _validate_reference(item.kost2_cost_center_id, cost_center_ids, "kost2_cost_center_id")
    return [
        _write_record(
            "accounting.posting_proposals_cash_register",
            item,
            client_id=client_id,
            fiscal_year_id=fiscal_year_id,
        )
        for item in body
    ]
