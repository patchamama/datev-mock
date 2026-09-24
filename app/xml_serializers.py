"""Hand-built XML rendering for the three DATEV DataContractSerializer shapes.

Built with plain string templates (not `xml.etree.ElementTree`) because the
real contract mixes a root-level default namespace with several *per-field*
namespace overrides (bare `xmlns="..."` re-declarations plus unused `d3p1`
prefixes) that ElementTree's serializer cannot reproduce byte-for-byte — it
always hoists namespaces to auto-generated `ns0`/`ns1` prefixes instead of
re-declaring a bare default per element. String templates give full control
over the exact shape while still producing well-formed XML (verified by the
test suite's own `ET.fromstring` round-trip).
"""
from __future__ import annotations

import dataclasses
from xml.sax.saxutils import escape

from app.models import (
    ACCOUNTING_SEQUENCE_PROCESSED_FIELD_ORDER,
    ACCOUNTING_TRANSACTION_KEY_FIELD_ORDER,
    ASSET_STOCKTAKING_FIELD_ORDER,
    BUSINESS_PARTNER_COMMON_NS_FIELDS,
    BUSINESS_PARTNER_FIELD_ORDER,
    CLIENT_FIELD_ORDER,
    CLIENT_RESOURCE_FIELD_ORDER,
    COST_CENTER_FIELD_ORDER,
    COST_SYSTEM_FIELD_ORDER,
    FISCAL_YEAR_FIELD_ORDER,
    GENERAL_LEDGER_ACCOUNT_FIELD_ORDER,
    OPEN_ITEM_FIELD_ORDER,
    POSTING_PROPOSAL_RULE_FIELD_ORDER,
    TERM_OF_PAYMENT_FIELD_ORDER,
    AccountingSequenceProcessed,
    AccountingTransactionKey,
    AssetStocktaking,
    Client,
    ClientResource,
    CostCenter,
    CostSystem,
    Creditor,
    Debitor,
    Echo,
    FiscalYear,
    GeneralLedgerAccount,
    OpenItem,
    PostingProposalRule,
    TermOfPayment,
)

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SERVICEBUS_NS = "http://xml.datev.de/Framework/ServiceBus/Contracts/V01"
CONNECT_CONTRACTS_NS = "http://schemas.datacontract.org/2004/07/Datev.Connect.Contracts"
ARRAYS_NS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"

ECHO_NS = "http://schemas.datacontract.org/2004/07/Datev.ApplicationHost.Server.DataObjects"
MASTER_DATA_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Sdd.Connect.PlugIn.Contracts.Resources"
)
ACCOUNTING_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Clients"
)
ACCOUNTING_PRODUCTIVITIES_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Productivities"
)

# --- Real-data reconciliation epic, W2 batch A ---
#
# Namespaces for the 6 newly XML-capable resources. `COST_SYSTEMS_NS` and
# `BUSINESS_PARTNERS_NS` are **confirmed** by real captures
# (`examples/cost-systems.xml`, `examples/debitors.xml`). The other 3 are
# **inferred by pattern** (`ArrayOf<PascalName>` / `...Contracts.<PascalName>`,
# the convention every other confirmed sample in this project follows) —
# flagged here explicitly, never presented as more certain than that. Note
# `BUSINESS_PARTNERS_NS` itself is evidence that the generic "namespace ==
# singular resource name" pattern isn't universal (debitors' real namespace
# is the *contract family* name `BusinessPartners`, not `Debitor`) — applied
# to `creditors` too by inference, since creditor/debitor are the same
# contract family.
FISCAL_YEAR_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.FiscalYear"
)
COST_SYSTEMS_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.CostSystems"
)
COST_CENTER_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.CostCenter"
)
BUSINESS_PARTNERS_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.BusinessPartners"
)
GENERAL_LEDGER_ACCOUNT_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.GeneralLedgerAccount"
)
ACCOUNTING_COMMON_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Common"
)

# --- Real-data reconciliation epic, W3 batch B ---
#
# Inferred by pattern (no direct real XML evidence for any of these 3
# endpoints — the "condense"/"accounting-sequences-processed"/"accounting-
# transaction-keys" real captures were all JSON content despite their
# `.xml` filenames, same quirk already noted for `fiscal_years` in W2).
# `OPEN_ITEM_NS` covers all 3 open-item endpoints identically
# (`accounts_payable`/`accounts_payable_condense`/
# `accounts_receivable_condense`) since they share one real underlying
# contract type (`OpenItem`) per the compiled spec doc and this project's
# own override-detection "ambiguous group" design.
OPEN_ITEM_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.OpenItem"
)
ACCOUNTING_SEQUENCE_PROCESSED_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts."
    "AccountingSequenceProcessed"
)
ACCOUNTING_TRANSACTION_KEY_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts."
    "AccountingTransactionKey"
)

# --- Real-data reconciliation epic, W4 batch C ---
#
# Inferred by pattern (no direct real XML evidence for either endpoint —
# both real captures returned empty `[]` for `posting_proposal_rules_
# incoming`/`outgoing`, and `terms-of-payment.xml`'s real capture is JSON
# content, same quirk already flagged for `fiscal_years` in W2).
# `POSTING_PROPOSAL_RULE_NS` covers both the incoming and outgoing endpoints
# identically, since they share one real underlying `PostingProposalRule`
# contract type per the compiled spec doc (same "one shared contract"
# precedent as `OPEN_ITEM_NS` above).
POSTING_PROPOSAL_RULE_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts."
    "PostingProposalRule"
)
TERM_OF_PAYMENT_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts."
    "TermOfPayment"
)

# --- Real-data reconciliation epic, W5 ---
#
# `assets_stocktakings` was missed by W1-W4's batching despite being one of
# the 15 accounting sub-resources in scope (caught during W5's final
# regression pass). Inferred by pattern — no real capture exists at all for
# this endpoint (`examples/info.txt` lists an attempt, but the file was
# never actually saved).
ASSET_STOCKTAKING_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts."
    "AssetStocktaking"
)

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'


def _render_field(name: str, value: object, ns_attr: str = "") -> str:
    if value is None:
        return f'<{name}{ns_attr} i:nil="true"/>'
    if isinstance(value, bool):
        # DataContractSerializer renders booleans lowercase (`true`/`false`),
        # confirmed by `examples/cost-systems.xml` (`IsActivatedForPostings`)
        # and `examples/debitors.xml` (`IsBusinessPartnerActive`) — Python's
        # `str(True)` would otherwise emit the wrong-case `True`.
        text = "true" if value else "false"
        return f"<{name}{ns_attr}>{escape(text)}</{name}>"
    if dataclasses.is_dataclass(value):
        # Nested single object (e.g. `Address.address_usage_type`,
        # `Creditor.accounting_information`, `Creditor.legal_person`) —
        # recurse into its own fields instead of `str()`-ing the instance
        # (see `_render_dataclass_fields`'s docstring for the bug this
        # avoids).
        return f"<{name}{ns_attr}>{_render_dataclass_fields(value)}</{name}>"
    if isinstance(value, list):
        # Nested array of dataclass items (e.g. `Creditor.addresses`/
        # `.banks`/`.communications`) — wrap each item in an element named
        # after its own class (no real DATEV evidence for the exact per-item
        # tag name here, since these fields are never populated in any real
        # capture this project has — `Address`/`BusinessPartnerBank`/
        # `Communication` are already the singular-of-the-field-name shape
        # this project's naming convention would produce anyway).
        if not value:
            return f"<{name}{ns_attr}/>"
        item_tag = type(value[0]).__name__
        items = "".join(
            f"<{item_tag}>{_render_dataclass_fields(item)}</{item_tag}>" for item in value
        )
        return f"<{name}{ns_attr}>{items}</{name}>"
    text = str(value)
    return f"<{name}{ns_attr}>{escape(text)}</{name}>"


def _render_dataclass_fields(instance: object) -> str:
    """Recursively render every field of a nested dataclass instance (e.g.
    `Address`/`BusinessPartnerBank`/`Communication`/
    `CreditorAccountingInformation`/`DebitorAccountingInformation`, and
    their own nested sub-objects like `AddressUsageType`) as child XML
    elements, in declaration order.

    P2 of `datev-mock-expand-nested-content.md`: previously `_render_field`
    unconditionally did `str(value)` on anything that wasn't `None`/`bool`
    — for a dataclass or list, that produced a broken Python `repr()`
    string inside the XML (the write-endpoints epic's P2 notes; the reason
    `Creditor`/`Debitor`'s nested fields were force-nilled for stored
    records, see `app/routers/accounting.py::_BUSINESS_PARTNER_NIL_FIELDS`).
    `_render_field` above now recurses into real elements via this helper
    instead, so `expand=all` content actually renders as well-formed XML."""
    return "".join(
        _render_field(_xml_tag(f.name), getattr(instance, f.name))
        for f in dataclasses.fields(instance)
    )


def _pascal(name: str) -> str:
    """Naive snake_case -> PascalCase (capitalize each `_`-separated word).

    Matches every confirmed real DATEV field name 1:1 (`cost_field` ->
    `CostField`, `is_business_partner_active` -> `IsBusinessPartnerActive`,
    etc. — see `examples/cost-systems.xml`/`examples/debitors.xml`), the
    well-evidenced convention this mock's whole JSON<->XML field-name
    mapping relies on."""
    return "".join(part.capitalize() for part in name.split("_"))


def _xml_tag(field_name: str) -> str:
    if field_name == "id":
        return "Id"
    if field_name == "parent":
        return "Parent"
    if field_name == "members_to_serialize":
        return "membersToSerialize"
    return _pascal(field_name)


def _field_value(record: object, field_name: str) -> object:
    # `parent`/`members_to_serialize` are synthetic (not real dataclass
    # fields) — every confirmed sample in this project always renders them
    # `i:nil="true"`.
    if field_name in ("parent", "members_to_serialize"):
        return None
    return getattr(record, field_name)


def _generic_ns_attr(field_name: str, common_ns_fields: frozenset = frozenset()) -> str:
    if field_name in ("id", "parent"):
        return f' xmlns="{SERVICEBUS_NS}"'
    if field_name == "members_to_serialize":
        return f' xmlns:d3p1="{ARRAYS_NS}" xmlns="{CONNECT_CONTRACTS_NS}"'
    if field_name in common_ns_fields:
        return f' xmlns:d3p1="{ACCOUNTING_COMMON_NS}"'
    return ""


def _render_generic_record(
    record: object, field_order: list[str], tag: str, common_ns_fields: frozenset = frozenset()
) -> str:
    fields = "".join(
        _render_field(
            _xml_tag(name), _field_value(record, name), _generic_ns_attr(name, common_ns_fields)
        )
        for name in field_order
    )
    return f"<{tag}>{fields}</{tag}>"


def _master_data_ns_attr(field_name: str) -> str:
    if field_name in ("Id", "Parent"):
        return f' xmlns="{SERVICEBUS_NS}"'
    if field_name == "membersToSerialize":
        return f' xmlns:d3p1="{ARRAYS_NS}" xmlns="{CONNECT_CONTRACTS_NS}"'
    return ""


def _accounting_ns_attr(field_name: str) -> str:
    if field_name in ("Id", "Parent"):
        return f' xmlns="{SERVICEBUS_NS}"'
    if field_name == "membersToSerialize":
        return f' xmlns:d3p1="{ARRAYS_NS}" xmlns="{CONNECT_CONTRACTS_NS}"'
    if field_name == "AccountingProductivities":
        return f' xmlns:d3p1="{ACCOUNTING_PRODUCTIVITIES_NS}"'
    return ""


def _serialize_client_resource(record: ClientResource) -> str:
    fields = "".join(
        _render_field(name, getattr(record, name), _master_data_ns_attr(name))
        for name in CLIENT_RESOURCE_FIELD_ORDER
    )
    return f"<ClientResource>{fields}</ClientResource>"


def serialize_client_resources(records: list[ClientResource]) -> str:
    body = "".join(_serialize_client_resource(r) for r in records)
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfClientResource xmlns:i="{XSI_NS}" xmlns="{MASTER_DATA_NS}">'
        f"{body}"
        "</ArrayOfClientResource>"
    )


def _serialize_client(record: Client) -> str:
    fields = "".join(
        _render_field(name, getattr(record, name), _accounting_ns_attr(name))
        for name in CLIENT_FIELD_ORDER
    )
    return f"<Client>{fields}</Client>"


def serialize_clients(records: list[Client]) -> str:
    body = "".join(_serialize_client(r) for r in records)
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfClient xmlns:i="{XSI_NS}" xmlns="{ACCOUNTING_NS}">'
        f"{body}"
        "</ArrayOfClient>"
    )


def serialize_echo(echo: Echo) -> str:
    return (
        f"{XML_DECLARATION}"
        f'<Echo xmlns:i="{XSI_NS}" xmlns="{ECHO_NS}">'
        f"<echo_message>{escape(echo.echo_message)}</echo_message>"
        f"<id>{escape(echo.id)}</id>"
        "</Echo>"
    )


# --- Real-data reconciliation epic, W2 batch A: fiscal_years, cost_systems,
# cost_centers, creditors, debitors, general_ledger_accounts XML negotiation.
# See the namespace constants' comments above for confirmed-vs-inferred
# status per endpoint.


def serialize_fiscal_years(records: list[FiscalYear]) -> str:
    body = "".join(
        _render_generic_record(r, FISCAL_YEAR_FIELD_ORDER, "FiscalYear") for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfFiscalYear xmlns:i="{XSI_NS}" xmlns="{FISCAL_YEAR_NS}">'
        f"{body}"
        "</ArrayOfFiscalYear>"
    )


def serialize_cost_systems(records: list[CostSystem]) -> str:
    # Repeated element is `CostSystems` (plural) — confirmed by
    # `examples/cost-systems.xml`, not the generically-expected singular.
    body = "".join(
        _render_generic_record(r, COST_SYSTEM_FIELD_ORDER, "CostSystems") for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfCostSystems xmlns:i="{XSI_NS}" xmlns="{COST_SYSTEMS_NS}">'
        f"{body}"
        "</ArrayOfCostSystems>"
    )


def serialize_cost_centers(records: list[CostCenter]) -> str:
    body = "".join(
        _render_generic_record(r, COST_CENTER_FIELD_ORDER, "CostCenter") for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfCostCenter xmlns:i="{XSI_NS}" xmlns="{COST_CENTER_NS}">'
        f"{body}"
        "</ArrayOfCostCenter>"
    )


def serialize_creditors(records: list[Creditor]) -> str:
    body = "".join(
        _render_generic_record(
            r, BUSINESS_PARTNER_FIELD_ORDER, "Creditor", BUSINESS_PARTNER_COMMON_NS_FIELDS
        )
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfCreditor xmlns:i="{XSI_NS}" xmlns="{BUSINESS_PARTNERS_NS}">'
        f"{body}"
        "</ArrayOfCreditor>"
    )


def serialize_debitors(records: list[Debitor]) -> str:
    body = "".join(
        _render_generic_record(
            r, BUSINESS_PARTNER_FIELD_ORDER, "Debitor", BUSINESS_PARTNER_COMMON_NS_FIELDS
        )
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfDebitor xmlns:i="{XSI_NS}" xmlns="{BUSINESS_PARTNERS_NS}">'
        f"{body}"
        "</ArrayOfDebitor>"
    )


def serialize_general_ledger_accounts(records: list[GeneralLedgerAccount]) -> str:
    body = "".join(
        _render_generic_record(r, GENERAL_LEDGER_ACCOUNT_FIELD_ORDER, "GeneralLedgerAccount")
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfGeneralLedgerAccount xmlns:i="{XSI_NS}" xmlns="{GENERAL_LEDGER_ACCOUNT_NS}">'
        f"{body}"
        "</ArrayOfGeneralLedgerAccount>"
    )


# --- Real-data reconciliation epic, W3 batch B: accounts_payable,
# accounts_payable_condense, accounts_receivable_condense,
# accounting_sequences_processed, accounting_transaction_keys XML
# negotiation. See the namespace constants' comments above for confirmed-
# vs-inferred status (all 5 are inferred by pattern — no direct real XML
# evidence exists for any of them).


def serialize_open_items(records: list[OpenItem]) -> str:
    """Shared serializer for all 3 open-item endpoints (`accounts_payable`,
    `accounts_payable_condense`, `accounts_receivable_condense`) — they
    share the exact same `OpenItem` shape, so the root/element tag and
    namespace are identical across all 3 call sites."""
    body = "".join(_render_generic_record(r, OPEN_ITEM_FIELD_ORDER, "OpenItem") for r in records)
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfOpenItem xmlns:i="{XSI_NS}" xmlns="{OPEN_ITEM_NS}">'
        f"{body}"
        "</ArrayOfOpenItem>"
    )


def serialize_accounting_sequences_processed(records: list[AccountingSequenceProcessed]) -> str:
    body = "".join(
        _render_generic_record(r, ACCOUNTING_SEQUENCE_PROCESSED_FIELD_ORDER, "AccountingSequenceProcessed")
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfAccountingSequenceProcessed xmlns:i="{XSI_NS}" xmlns="{ACCOUNTING_SEQUENCE_PROCESSED_NS}">'
        f"{body}"
        "</ArrayOfAccountingSequenceProcessed>"
    )


def serialize_accounting_transaction_keys(records: list[AccountingTransactionKey]) -> str:
    body = "".join(
        _render_generic_record(r, ACCOUNTING_TRANSACTION_KEY_FIELD_ORDER, "AccountingTransactionKey")
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfAccountingTransactionKey xmlns:i="{XSI_NS}" xmlns="{ACCOUNTING_TRANSACTION_KEY_NS}">'
        f"{body}"
        "</ArrayOfAccountingTransactionKey>"
    )


# --- Real-data reconciliation epic, W4 batch C: posting_proposal_rules_
# incoming/outgoing, terms_of_payment XML negotiation. See the namespace
# constants' comments above — both inferred by pattern, no direct real XML
# evidence for either. Nested/list-typed fields (`assignment_criteria`/
# `posting_proposal_information` on PostingProposalRule, `due_in_days`/
# `due_as_period` on TermOfPayment) are excluded from the rendered shape,
# same precedent as `CostCenter`'s `cost_rates`/`properties` in W2 — they
# stay JSON-only.


def serialize_posting_proposal_rules(records: list[PostingProposalRule]) -> str:
    """Shared serializer for both `posting_proposal_rules_incoming` and
    `posting_proposal_rules_outgoing` — they share the exact same
    `PostingProposalRule` shape, so the root/element tag and namespace are
    identical across both call sites (same precedent as
    `serialize_open_items`)."""
    body = "".join(
        _render_generic_record(r, POSTING_PROPOSAL_RULE_FIELD_ORDER, "PostingProposalRule")
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfPostingProposalRule xmlns:i="{XSI_NS}" xmlns="{POSTING_PROPOSAL_RULE_NS}">'
        f"{body}"
        "</ArrayOfPostingProposalRule>"
    )


def serialize_terms_of_payment(records: list[TermOfPayment]) -> str:
    body = "".join(
        _render_generic_record(r, TERM_OF_PAYMENT_FIELD_ORDER, "TermOfPayment") for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfTermOfPayment xmlns:i="{XSI_NS}" xmlns="{TERM_OF_PAYMENT_NS}">'
        f"{body}"
        "</ArrayOfTermOfPayment>"
    )


def serialize_assets_stocktakings(records: list[AssetStocktaking]) -> str:
    """Inferred by pattern (epic `datev-mock-real-data-reconciliation`, W5 —
    no real capture exists for this endpoint at all). `general_ledger_account`
    (nested) is excluded from the rendered shape, same precedent as
    `CostCenter`'s `cost_rates`/`properties`."""
    body = "".join(
        _render_generic_record(r, ASSET_STOCKTAKING_FIELD_ORDER, "AssetStocktaking")
        for r in records
    )
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfAssetStocktaking xmlns:i="{XSI_NS}" xmlns="{ASSET_STOCKTAKING_NS}">'
        f"{body}"
        "</ArrayOfAssetStocktaking>"
    )
