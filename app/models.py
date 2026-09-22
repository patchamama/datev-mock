"""Dataclasses backing the DATEV mock's three response shapes.

Field names intentionally mirror the real DATEV DataContractSerializer XML
element names (PascalCase for most, camelCase for `membersToSerialize`) so
that `xml_serializers.py` can render them directly without a translation
table. No real DATEV data is embedded here — only shapes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClientResource:
    """Master-data `ClientResource` — exact 42-field layout, in order.

    Order matters for `xml_serializers.py`, which renders fields in
    declaration order to match the real contract's element order.
    """

    Id: str
    Parent: Optional[str] = None
    membersToSerialize: Optional[str] = None
    AccountHolderForBilling: Optional[str] = None
    AuthorizedRecipientForLegalPerson: Optional[str] = None
    AuthorizedRecipientForNaturalPerson: Optional[str] = None
    ClientSince: Optional[str] = None
    ClientTo: Optional[str] = None
    CorrespondenceRecipient: Optional[str] = None
    DifferingName: Optional[str] = None
    EstablishmentId: Optional[str] = None
    EstablishmentName: Optional[str] = None
    EstablishmentNumber: Optional[str] = None
    EstablishmentShortName: Optional[str] = None
    FunctionalAreaId: Optional[str] = None
    FunctionalAreaName: Optional[str] = None
    FunctionalAreaShortName: Optional[str] = None
    IdentificationCheckedOn: Optional[str] = None
    IdentificationComment: Optional[str] = None
    IdentificationStatus: Optional[str] = None
    InvoiceRecipients: Optional[str] = None
    LeadId: Optional[str] = None
    LegalPersonId: Optional[str] = None
    Name: str = ""
    NaturalPersonId: Optional[str] = None
    Note: Optional[str] = None
    Number: int = 0
    OnlineRevision: Optional[str] = None
    OrganizationId: Optional[str] = None
    OrganizationName: Optional[str] = None
    OrganizationNumber: Optional[str] = None
    Revision: Optional[str] = None
    RiskAssessment: Optional[str] = None
    RiskAssessmentDate: Optional[str] = None
    RiskAssessmentReason: Optional[str] = None
    Status: str = "active"
    StayRegistered: Optional[str] = None
    Timestamp: str = ""
    TransparencyRegister: Optional[str] = None
    TransparencyRegisterCheckedOn: Optional[str] = None
    TransparencyRegisterComment: Optional[str] = None
    Type: str = "legal_person"


# Declaration order of ClientResource's fields, used by the XML serializer to
# guarantee element order independent of dataclass introspection quirks.
CLIENT_RESOURCE_FIELD_ORDER = [
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


@dataclass
class CompanyData:
    """JSON-only accounting company data (`company_data.creditor_identifier`).

    The real XML `CompanyData` element is always `i:nil="true"` (see
    `test_accounting_productivities_and_company_data_are_nil`), so this
    payload is only ever consumed by the JSON content-negotiation branch.
    """

    creditor_identifier: str


@dataclass
class Client:
    """Accounting `Client` — 8-field XML layout, plus JSON-only extras."""

    Id: str
    ClientGuid: str
    Name: str
    Number: int
    Parent: Optional[str] = None
    membersToSerialize: Optional[str] = None
    AccountingProductivities: Optional[str] = None
    CompanyData: Optional[str] = None  # always None -> always i:nil in XML
    company_data: Optional[CompanyData] = None  # JSON-only, may be populated


CLIENT_FIELD_ORDER = [
    "Id",
    "Parent",
    "membersToSerialize",
    "AccountingProductivities",
    "ClientGuid",
    "CompanyData",
    "Name",
    "Number",
]


@dataclass
class Echo:
    """Diagnostics `Echo` — generated fresh per request."""

    echo_message: str
    id: str


@dataclass
class Addressee:
    """Master-data `Addressee` — flat top-level fields only.

    Real DATEV `Addressee` also carries `detail`/`addresses`/`communications`/
    `bank_accounts`/`tax_offices`/`contact_persons`, but per the official spec
    those are only included when the request uses `expand=...`; this mock
    does not implement `expand`, so — consistent with real API behavior when
    `expand` is absent — those nested collections are simply not modeled or
    served here.

    `type` (`natural_person`|`legal_person`) is a flat enum with parallel
    sibling fields for each type (no real OpenAPI polymorphism), per the
    compiled spec doc.
    """

    id: str
    type: str
    status: str
    timestamp: str
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    current_short_name: Optional[str] = None
    surrogate_name: Optional[str] = None
    # natural_person-only (by convention/description, not schema-enforced)
    date_of_birth: Optional[str] = None
    etin: Optional[str] = None
    firstname: Optional[str] = None
    sex: Optional[str] = None
    current_surname: Optional[str] = None
    tax_identification_number: Optional[str] = None
    # legal_person-only (by convention/description, not schema-enforced)
    current_company_name: Optional[str] = None
    date_of_foundation: Optional[str] = None
    current_legal_form_id: Optional[str] = None


@dataclass
class Bank:
    """Master-data `Bank` — full flat schema (small, no nesting)."""

    id: str
    bank_code: str
    bic: str
    city: str
    country_code: str
    name: str
    standard: bool
    timestamp: str


# --- Accounting extension, Phase B batch B1 (extended-endpoints epic) ---
#
# Field names/shapes per the compiled OpenAPI reference (session scratchpad
# `datev-endpoint-specs.md`) and the locked-in fake-data contract recorded in
# `odd/tasks/datev-mock-extended-endpoints.md`'s B0 progress entry. Per the
# epic's cross-phase decision, none of these are filtered by their URL path
# params (`client_id`/`fiscal_year_id`/`cost_system_id`) — every list call
# returns the same fixed fake dataset regardless of the ids in the path.


@dataclass
class FiscalYear:
    """Accounting `fiscal-year` — client-level list, not fiscal-year-scoped."""

    id: str  # YYYYMMDD, first day of the fiscal year
    account_system: int
    currency_code: str
    legal_form: str
    taxation_method: str
    national_right: str
    is_locked: bool
    account_length: Optional[int] = None
    advance_turnover_tax_return: Optional[str] = None
    basis_of_checking_account_function: Optional[str] = None
    begin: Optional[str] = None
    client_number: Optional[int] = None
    consultant_number: Optional[int] = None
    cost_length: Optional[int] = None
    creditor_term_of_payment_id: Optional[int] = None
    debitor_term_of_payment_id: Optional[int] = None
    end: Optional[str] = None
    is_invoice_date_check_on: Optional[bool] = None
    is_using_delivery_date: Optional[bool] = None
    is_using_receivable_type: Optional[bool] = None
    method_of_determining_net_income: Optional[str] = None


@dataclass
class CostSystem:
    """Accounting `cost-system`. Spec types `number` as "number" (format
    "short") despite being integer-valued in practice — emitted as a plain
    JSON int here."""

    id: str  # maxLength 1
    short_name: str
    is_activated_for_postings: bool
    number: int
    cost_field: Optional[str] = None


@dataclass
class CostRate:
    """`cost-center.cost_rates[]` entry. `valid_from`/`valid_to` are
    integer-encoded dates (e.g. `20161201`), not date-time strings — an
    explicit spec quirk, not a typo."""

    valid_from: int
    valid_to: int
    rate: float


@dataclass
class CostCenter:
    id: str
    long_name: str
    short_name: str
    creation_date: str
    cost_rates: list[CostRate] = field(default_factory=list)
    properties: list[dict] = field(default_factory=list)
    date_last_modification: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None
    postable_from: Optional[str] = None
    postable_to: Optional[str] = None
    reference_value: Optional[str] = None
    responsible: Optional[str] = None


@dataclass
class NaturalPerson:
    """Shared by `creditor`/`debitor` (`datev.natural-person`)."""

    firstname: str
    surname: str
    date_of_birth: Optional[str] = None
    degree: Optional[str] = None
    name_prefix: Optional[str] = None
    title_of_nobility: Optional[str] = None


@dataclass
class LegalPerson:
    """Shared by `creditor`/`debitor` (`datev.legal-person`)."""

    legal_name: str
    enterprise_purpose: Optional[str] = None
    legal_form: Optional[str] = None


@dataclass
class NotSpecifiedPerson:
    """Shared by `creditor`/`debitor` (`datev.not-specified-person`)."""

    name: str


@dataclass
class CreditorAccountingInformation:
    """`datev.creditor-accounting-information` — partial, unasserted by RED;
    populated for shape-completeness only."""

    currency_management: Optional[str] = None
    is_insolvent: Optional[bool] = None
    is_various_account: Optional[bool] = None
    language: Optional[str] = None
    output_destination: Optional[str] = None
    payment_medium: Optional[str] = None
    term_of_payment_id: Optional[int] = None


@dataclass
class DebitorAccountingInformation:
    """`datev.debitor-accounting-information` — richer than the creditor
    equivalent; not asserted by RED at all (epic doc: GREEN has full
    latitude here), populated for shape-completeness only."""

    account_statement: Optional[str] = None
    credit_limit: Optional[int] = None
    currency_management: Optional[str] = None
    direct_debit: Optional[str] = None
    dunning_procedure: Optional[str] = None
    interest_calculation: Optional[str] = None
    is_insolvent: Optional[bool] = None
    is_various_account: Optional[bool] = None
    language: Optional[str] = None
    output_destination: Optional[str] = None
    term_of_payment_id: Optional[int] = None


@dataclass
class Creditor:
    """Accounting `creditor`. Uses the same "no real polymorphism" pattern as
    `Addressee` (Phase A): a flat `legal_entity_type` enum plus co-located,
    optional `natural_person`/`legal_person`/`not_specified_person` sibling
    objects, gated only by convention/description text."""

    id: str
    account_number: int
    addressee_id: str
    business_partner_number: str
    legal_entity_type: str
    short_name: str
    natural_person: Optional[NaturalPerson] = None
    legal_person: Optional[LegalPerson] = None
    not_specified_person: Optional[NotSpecifiedPerson] = None
    accounting_information: Optional[CreditorAccountingInformation] = None
    alternative_search_name: Optional[str] = None
    business_partner_relation_id: Optional[str] = None
    caption: Optional[str] = None
    correspondence_title: Optional[str] = None
    date_last_modification: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    is_business_partner_active: Optional[bool] = None
    is_organization_business_partner: Optional[bool] = None
    salutation: Optional[str] = None
    third_party_number: Optional[str] = None


@dataclass
class Debitor:
    """Accounting `debitor` — structurally identical to `creditor` for the
    shared top-level/business-partner fields, with a richer
    `accounting_information` sub-schema (see `DebitorAccountingInformation`)."""

    id: str
    account_number: int
    addressee_id: str
    business_partner_number: str
    legal_entity_type: str
    short_name: str
    natural_person: Optional[NaturalPerson] = None
    legal_person: Optional[LegalPerson] = None
    not_specified_person: Optional[NotSpecifiedPerson] = None
    accounting_information: Optional[DebitorAccountingInformation] = None
    alternative_search_name: Optional[str] = None
    business_partner_relation_id: Optional[str] = None
    caption: Optional[str] = None
    correspondence_title: Optional[str] = None
    date_last_modification: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    is_business_partner_active: Optional[bool] = None
    is_organization_business_partner: Optional[bool] = None
    salutation: Optional[str] = None
    third_party_number: Optional[str] = None


@dataclass
class GeneralLedgerAccountTaxRate:
    """`general-ledger-account.tax_rates[]` entry."""

    tax_rate: float
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None


@dataclass
class GeneralLedgerAccount:
    """Accounting `general-ledger-account`. `main_function`/
    `main_function_number`/`additional_function` are typed as plain
    `integer` in the spec (valid values only documented in free-text
    description, no OpenAPI `enum`) — hardcoded lookup sets are used in
    `app/fake_data.py` instead of an open int range, per the epic doc's
    explicit quirk note."""

    id: str
    account_number: int
    caption: str
    main_function: int
    main_function_number: int
    additional_function: Optional[int] = None
    function_description: Optional[str] = None
    function_extension: Optional[int] = None
    tax_rates: list[GeneralLedgerAccountTaxRate] = field(default_factory=list)


# --- Accounting extension, Phase B batch B2 (extended-endpoints epic) ---
#
# Field names/shapes per the compiled OpenAPI reference (session scratchpad
# `datev-endpoint-specs.md`) and the locked-in fake-data contract recorded in
# `odd/tasks/datev-mock-extended-endpoints.md`'s B0 progress entry. Same
# "no path-param filtering" convention as batch B1's dataclasses above.


@dataclass
class OpenItem:
    """Accounting `accounts-payable` (endpoint #6) / `accounts-payable/condense`
    (#2) / `accounts-receivable/condense` (#3) — the three share a single
    schema per the compiled spec doc; condense is a server-side aggregation,
    not a different shape. `dunning_level`/`dunning_date1/2/3` are
    receivable-only fields (absent from `accounts-payable`)."""

    id: str
    account_number: int
    amount_debit: float
    amount_credit: float
    amount_entered: float
    currency_code: str
    evidence_type: str
    debit_credit_identifier: str
    is_cleared: bool
    open_balance_of_item: float
    accounting_sequence_id: Optional[str] = None
    assessment_year: Optional[int] = None
    assigned_due_date: Optional[str] = None
    balance_type: Optional[str] = None
    contra_account_number: Optional[int] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    due_days: Optional[int] = None
    is_condensed: Optional[bool] = None
    posting_description: Optional[str] = None
    tax_rate: Optional[float] = None
    term_of_payment_id: Optional[int] = None
    # receivable-only (see class docstring)
    dunning_level: Optional[str] = None
    dunning_date1: Optional[str] = None
    dunning_date2: Optional[str] = None
    dunning_date3: Optional[str] = None


@dataclass
class AccountingSequenceProcessed:
    """Accounting `accounting-sequence-read` (endpoint #4)."""

    id: str
    accounting_sequence_id: str
    description: str
    date_from: str
    date_to: str
    is_committed: bool
    record_type: str
    accounting_reason: str
    application_information: Optional[str] = None
    initials: Optional[str] = None
    inspection_status: Optional[str] = None
    mark_of_origin: Optional[str] = None


@dataclass
class AccountingTransactionKey:
    """Accounting `accounting-transaction-keys` (endpoint #5)."""

    id: str
    number: int
    tax_rate: float
    is_tax_rate_selectable: bool
    caption: Optional[str] = None
    additional_function: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@dataclass
class GeneralLedgerAccountMinimal:
    """`stocktaking_record.general_ledger_account` —
    `datev.general-ledger-account-minimal`, resolved."""

    account_number: int
    caption: str


@dataclass
class AssetStocktaking:
    """Accounting `stocktaking_record` (endpoint #7, `assets/stocktakings`).
    `asset_number`/`inventory_number` are the spec's own two `required`
    fields."""

    id: str
    asset_number: int
    inventory_number: str
    accounting_reason: int
    general_ledger_account: Optional[GeneralLedgerAccountMinimal] = None
    inventory_name: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    stocktaking_date: Optional[str] = None
    unit: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None


@dataclass
class AssignmentCriteria:
    """`datev.assignment-criteria-invoices`, shared by both posting-proposal-
    rule directions (endpoints #13/#14)."""

    name: str
    tax_rate: float
    goods_and_services: Optional[str] = None


@dataclass
class PostingProposalInformation:
    """`posting_proposal_information[]` entry, shared shape for incoming and
    outgoing invoices — only the allowed `origin_of_posting_description`
    values differ (outgoing has two extra enum values), which this mock
    doesn't enforce at the dataclass level."""

    accounting_transaction_key: int
    account_number: int
    origin_of_posting_description: str
    business_partner_account_number: Optional[int] = None
    kost1_cost_center_id: Optional[str] = None
    kost2_cost_center_id: Optional[str] = None
    posting_description: Optional[str] = None


@dataclass
class PostingProposalRule:
    """Accounting `posting-proposal-rule-incoming-invoices` (#13) /
    `posting-proposal-rule-outgoing-invoices` (#14) — identical shape per the
    compiled spec doc, reused for both directions."""

    id: str
    uncertain_label: bool
    assignment_criteria: AssignmentCriteria
    posting_proposal_information: list[PostingProposalInformation] = field(default_factory=list)
    creation_date: Optional[str] = None
    last_used_date: Optional[str] = None


@dataclass
class DueDate:
    """`datev.due-date`, required: `day_of_month`, `related_month`."""

    related_month: str
    day_of_month: int


@dataclass
class Period:
    """`datev.period`, required: `due_date_net`, `invoice_day_of_month`."""

    invoice_day_of_month: int
    due_date_net: DueDate
    due_date_cash_discount1: Optional[DueDate] = None
    due_date_cash_discount2: Optional[DueDate] = None


@dataclass
class DueInDays:
    """`datev.due-in-days`."""

    due_in_days: int
    cash_discount1_days: Optional[int] = None
    cash_discount2_days: Optional[int] = None


@dataclass
class DueAsPeriod:
    """`datev.due-as-period`, required: `period1`."""

    period1: Period
    period2: Optional[Period] = None
    period3: Optional[Period] = None


@dataclass
class TermOfPayment:
    """Accounting `term-of-payment` (endpoint #15). `caption` is the spec's
    sole `required` field. `due_type` gates which of `due_in_days`/
    `due_as_period` is populated (parallel-fields convention, same pattern as
    `Addressee.type` and `creditor`/`debitor.legal_entity_type`)."""

    id: str
    caption: str
    due_type: str
    due_in_days: Optional[DueInDays] = None
    due_as_period: Optional[DueAsPeriod] = None
    cash_discount1_percentage: Optional[float] = None
    cash_discount2_percentage: Optional[float] = None
