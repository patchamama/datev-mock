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
class HistoricalValue:
    """One entry of an `Addressee` "historical field" array
    (`company_names`/`short_names`/`legal_form_ids`/`surnames`) — the
    `current_X` (scalar) + `X` (array of `{value[, valid_from]}`) pattern
    documented by DATEV's Client Master Data API. Real evidence
    (`examples/addressees.xml`, real-data reconciliation epic W4): `value`
    is always present; `valid_from` is present on only a small minority of
    entries (7/103 `company_names` entries, 6/105 `short_names`, 5/75
    `legal_form_ids`, 0/8 `surnames`) — genuinely optional, not just
    schema-typed as such."""

    value: str
    valid_from: Optional[str] = None


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

    `company_names`/`short_names`/`legal_form_ids`/`surnames` are the
    "historical field" arrays confirmed by direct evidence against the full
    111-record `examples/addressees.xml` sample (real-data reconciliation
    epic, W4) — see `HistoricalValue`. `company_names`/`legal_form_ids` are
    legal_person-only (0 occurrences on any natural_person record);
    `surnames` is natural_person-only (0 occurrences on any legal_person
    record); `short_names` is shared by both types and tracks
    `current_short_name`'s own presence 1:1 in the real sample.
    """

    id: str
    type: str
    status: str
    timestamp: str
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    current_short_name: Optional[str] = None
    short_names: Optional[list[HistoricalValue]] = None
    surrogate_name: Optional[str] = None
    # natural_person-only (by convention/description, not schema-enforced)
    date_of_birth: Optional[str] = None
    etin: Optional[str] = None
    firstname: Optional[str] = None
    sex: Optional[str] = None
    current_surname: Optional[str] = None
    surnames: Optional[list[HistoricalValue]] = None
    tax_identification_number: Optional[str] = None
    # legal_person-only (by convention/description, not schema-enforced)
    current_company_name: Optional[str] = None
    company_names: Optional[list[HistoricalValue]] = None
    date_of_foundation: Optional[str] = None
    current_legal_form_id: Optional[str] = None
    legal_form_ids: Optional[list[HistoricalValue]] = None


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
    """Accounting `fiscal-year` — client-level list, not fiscal-year-scoped.

    Expanded to the real 23-field shape confirmed by a live-installation
    capture (`examples/fiscal-years.xml`, JSON content despite the filename;
    see `odd/tasks/datev-mock-real-data-reconciliation.md` W2). Only
    `basis_of_checking_account_function`, `debitor_term_of_payment_id`,
    `legal_form`, `method_of_determining_net_income` are genuinely optional
    (absent, not `null`, on some real records) — every other field is
    present on every observed record."""

    id: str  # YYYYMMDD, first day of the fiscal year
    account_length: int
    account_system: int
    advance_turnover_tax_return: str
    begin: str
    end: str
    client_number: int
    consultant_number: int
    cost_length: int
    creditor_term_of_payment_id: int
    currency_code: str
    is_invoice_date_check_on: bool
    is_locked: bool
    is_using_delivery_date: bool
    is_using_individual_referencesystem: bool
    is_using_receivable_type: bool
    is_using_referencesystem: bool
    national_right: str
    taxation_method: str
    basis_of_checking_account_function: Optional[str] = None
    debitor_term_of_payment_id: Optional[int] = None
    legal_form: Optional[str] = None
    method_of_determining_net_income: Optional[str] = None


# Declaration order of the DataContractSerializer XML element layout,
# inferred by pattern (no direct real XML evidence for this endpoint — see
# `app/xml_serializers.py`'s module docstring). `parent`/`members_to_serialize`
# are synthetic (not real dataclass fields, always nil), matching the
# `Id`/`Parent`/`membersToSerialize` preamble observed on every confirmed
# real DataContractSerializer sample in this project.
FISCAL_YEAR_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "account_length",
    "account_system",
    "advance_turnover_tax_return",
    "basis_of_checking_account_function",
    "begin",
    "client_number",
    "consultant_number",
    "cost_length",
    "creditor_term_of_payment_id",
    "currency_code",
    "debitor_term_of_payment_id",
    "end",
    "is_invoice_date_check_on",
    "is_locked",
    "is_using_delivery_date",
    "is_using_individual_referencesystem",
    "is_using_receivable_type",
    "is_using_referencesystem",
    "legal_form",
    "method_of_determining_net_income",
    "national_right",
    "taxation_method",
]


@dataclass
class CostSystem:
    """Accounting `cost-system`. Spec types `number` as "number" (format
    "short") despite being integer-valued in practice — emitted as a plain
    JSON int here. `cost_field` is a real **int** field, confirmed by a live
    capture (`examples/cost-systems.xml`, real XML — `CostField` element,
    always present on every sampled record) — corrected from an earlier,
    unevidenced `Optional[str]` guess."""

    id: str  # maxLength 1
    short_name: str
    is_activated_for_postings: bool
    number: int
    cost_field: int


# Declaration order confirmed by real XML (`examples/cost-systems.xml`):
# `Id`/`Parent`/`membersToSerialize` preamble, then the remaining fields in
# alphabetical PascalCase order. Repeated element name is **`CostSystems`**
# (plural) — a real, confirmed quirk, not the generically-expected singular
# `CostSystem`.
COST_SYSTEM_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "cost_field",
    "is_activated_for_postings",
    "number",
    "short_name",
]


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


# Declaration order for the inferred-by-pattern XML shape (no real XML
# evidence for this endpoint — epic doc confirms no new field evidence
# either). `Id`/`Parent`/`membersToSerialize` preamble, then the remaining
# *scalar* fields in alphabetical PascalCase order. `cost_rates`/`properties`
# are deliberately **excluded**: there's zero real evidence these array
# fields exist in the XML contract at all (unlike `Client.company_data`,
# which has a confirmed JSON-only precedent), so inventing a nested XML
# shape for them would be pure guesswork — they stay JSON-only until real
# evidence arrives.
COST_CENTER_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "creation_date",
    "date_last_modification",
    "email",
    "long_name",
    "note",
    "postable_from",
    "postable_to",
    "reference_value",
    "responsible",
    "short_name",
]


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
    """Accounting `creditor`. Real JSON confirmed 13 top-level fields
    (`examples/creditors.xml`, JSON content) — 11 always present, 2
    genuinely optional (`eu_vat_id_country_code`/`eu_vat_id_number`, absent
    on some records). `natural_person`/`legal_person`/`not_specified_person`
    (this project's own earlier "no real polymorphism" convention, same
    pattern as `Addressee`) and `accounting_information` are never observed
    in the real default (non-`expand`) response — corrected by W1/W2 to stay
    unpopulated by default, kept only as latent fields for a possible future
    `expand=all` implementation. `addresses`/`banks`/`communications`/
    `complimentary_close` are additional always-nil fields confirmed by
    debitors' real XML (see `Debitor` below) — inferred to apply here too
    since creditor/debitor share the same `BusinessPartners` contract
    family."""

    id: str
    account_number: int
    addressee_id: str
    business_partner_number: str
    business_partner_relation_id: str
    caption: str
    date_last_modification: str
    is_business_partner_active: bool
    is_organization_business_partner: bool
    legal_entity_type: str
    short_name: str
    accounting_information: Optional[CreditorAccountingInformation] = None
    addresses: Optional[str] = None
    alternative_search_name: Optional[str] = None
    banks: Optional[str] = None
    communications: Optional[str] = None
    complimentary_close: Optional[str] = None
    correspondence_title: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    legal_person: Optional[LegalPerson] = None
    natural_person: Optional[NaturalPerson] = None
    not_specified_person: Optional[NotSpecifiedPerson] = None
    salutation: Optional[str] = None
    third_party_number: Optional[str] = None


@dataclass
class Debitor:
    """Accounting `debitor` — structurally identical to `creditor` for the
    shared top-level/business-partner fields, with a richer
    `accounting_information` sub-schema (see `DebitorAccountingInformation`).
    Real **XML** confirmed (`examples/debitors.xml`, real capture): same 13
    top-level fields as `creditor` (PascalCase), plus the full list of
    nested/optional fields this project never modeled before —
    `AccountingInformation`, `Addresses`, `AlternativeSearchName`, `Banks`,
    `Communications`, `ComplimentaryClose`, `CorrespondenceTitle`,
    `LegalPerson`, `NaturalPerson`, `NotSpecifiedPerson`, `Salutation`,
    `ThirdPartyNumber` — every one of them observed as `i:nil="true"` on
    every sampled record, never populated by fake data (see
    `app/fake_data.py::_generate_debitors`)."""

    id: str
    account_number: int
    addressee_id: str
    business_partner_number: str
    business_partner_relation_id: str
    caption: str
    date_last_modification: str
    is_business_partner_active: bool
    is_organization_business_partner: bool
    legal_entity_type: str
    short_name: str
    accounting_information: Optional[DebitorAccountingInformation] = None
    addresses: Optional[str] = None
    alternative_search_name: Optional[str] = None
    banks: Optional[str] = None
    communications: Optional[str] = None
    complimentary_close: Optional[str] = None
    correspondence_title: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    legal_person: Optional[LegalPerson] = None
    natural_person: Optional[NaturalPerson] = None
    not_specified_person: Optional[NotSpecifiedPerson] = None
    salutation: Optional[str] = None
    third_party_number: Optional[str] = None


# Shared field order for both `Creditor` and `Debitor` XML — **confirmed**
# by real evidence for `Debitor` (`examples/debitors.xml`: `Id`/`Parent`/
# `membersToSerialize` preamble, then every remaining field in alphabetical
# PascalCase order); applied to `Creditor` too by inference (same
# `BusinessPartners` contract family, never directly observed as XML but
# structurally identical per the real JSON evidence).
BUSINESS_PARTNER_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "account_number",
    "accounting_information",
    "addressee_id",
    "addresses",
    "alternative_search_name",
    "banks",
    "business_partner_number",
    "business_partner_relation_id",
    "caption",
    "communications",
    "complimentary_close",
    "correspondence_title",
    "date_last_modification",
    "eu_vat_id_country_code",
    "eu_vat_id_number",
    "is_business_partner_active",
    "is_organization_business_partner",
    "legal_entity_type",
    "legal_person",
    "natural_person",
    "not_specified_person",
    "salutation",
    "short_name",
    "third_party_number",
]

# Fields that carry the extra `xmlns:d3p1=".../Contracts.Common"` namespace
# override when `i:nil="true"` — confirmed by `examples/debitors.xml` for
# exactly these 6 fields (array/nested-object types); every other nil field
# on `Creditor`/`Debitor` renders with no extra namespace attribute.
BUSINESS_PARTNER_COMMON_NS_FIELDS = frozenset(
    {"addresses", "banks", "communications", "legal_person", "natural_person", "not_specified_person"}
)


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
    explicit quirk note. `function_extension` is a real field confirmed by a
    live capture (`examples/general-ledger-accounts.xml`, JSON content) —
    the real 7-field shape is `account_number`, `additional_function`,
    `caption`, `function_extension`, `id`, `main_function`,
    `main_function_number`; `function_description` is kept as an extra,
    unconfirmed field (pre-existing, not contradicted by real evidence)."""

    id: str
    account_number: int
    caption: str
    main_function: int
    main_function_number: int
    function_extension: int
    additional_function: Optional[int] = None
    function_description: Optional[str] = None
    tax_rates: list[GeneralLedgerAccountTaxRate] = field(default_factory=list)


# Declaration order for the inferred-by-pattern XML shape (no real XML
# evidence for this endpoint). `Id`/`Parent`/`membersToSerialize` preamble,
# then the remaining *scalar* fields in alphabetical PascalCase order.
# `tax_rates` is excluded for the same "no real evidence this array field
# exists in XML" reason as `CostCenter.cost_rates`/`.properties` — see that
# field-order list's comment.
GENERAL_LEDGER_ACCOUNT_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "account_number",
    "additional_function",
    "caption",
    "function_description",
    "function_extension",
    "main_function",
    "main_function_number",
]


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
    not a different shape. `has_dunning_block` is real (per
    `examples/accounts-receivable-condense.xml` and `examples/condense.xml`,
    both JSON content) and present on **both** payable and receivable
    records — replaces this project's earlier invented `dunning_level`
    field, which real evidence confirmed does not exist (epic
    `datev-mock-real-data-reconciliation`, W1).

    Expanded to the real ~19-field shared shape confirmed directly against
    both real capture files (W3) — every field below except the
    `amount_debit`/`amount_credit`/optional group was observed on **100%**
    of records in **both** `examples/condense.xml` (accounts-payable/
    condense, 3642 records) and `examples/accounts-receivable-condense.xml`
    (3455 records), counted directly (`grep -o` occurrence counts against
    the real capture files, never printed/copied as values).

    **W3 correction to the epic doc's field table**: the epic doc (and the
    W3 task brief derived from it) claimed `amount_credit` is payable-only
    and `amount_debit`/`due_date`/`due_days`/`term_of_payment_id` are
    receivable-only. Direct evidence contradicts this — verified by
    counting occurrences, not reading the single first-record summary the
    epic doc's table was apparently based on:
      - `amount_debit`/`amount_credit` are **mutually exclusive per record**
        (driven by `debit_credit_identifier` S/H), on **both** payable and
        receivable alike — counts sum to exactly the total record count on
        both sides (e.g. payable: 1788 + 1854 = 3642 = total records).
      - `due_date`/`due_days`/`term_of_payment_id` are present on ~49% of
        records on **both** payable and receivable (payable: 1781/3642;
        receivable: 1706/3455) — genuinely optional, not receivable-only.
      - `balancing_type` (~88-89%), `contra_account_number` (~98.7-98.9%),
        `document_field2` (~51%), `kost1_cost_center_id` (~95-97%) are all
        optional at matching rates on both sides too.
    So payable and receivable are (contrary to the epic doc) effectively
    the **same** schema in practice, aside from `dunning_date1/2/3`
    (receivable-only per this project's pre-existing design; W1 found zero
    real evidence either confirming or contradicting them, and this batch's
    direct field-presence count confirms 0 occurrences of any of the three
    in either capture file — left untouched, per W1/W3 instructions).

    `amount_entered`/`currency_code`/`assessment_year`/`assigned_due_date`/
    `balance_type` are this project's own pre-existing, unconfirmed fields
    (not part of the real field set above) — kept as-is, not contradicted
    by real evidence, matching the W2 `function_description` precedent for
    handling pre-existing unevidenced fields. Note `balance_type` is a
    distinct, separate field from the newly-added real `balancing_type` —
    the similar names are coincidental, not a rename."""

    # --- real, always-present fields (100% on both capture files) ---
    id: str
    account_number: int
    accounting_sequence_id: str
    date: str
    debit_credit_identifier: str
    document_field1: str
    evidence_type: str
    has_interest_block: bool
    is_cleared: bool
    is_condensed: bool
    open_balance_of_item: float
    open_item_number: str
    payment_method: str
    posting_description: str
    posting_record_number: int
    tax_rate: float
    # --- pre-existing, unconfirmed fields (kept, not contradicted) ---
    amount_entered: float
    currency_code: str
    # --- real, genuinely optional fields (same presence rate both sides) ---
    amount_credit: Optional[float] = None
    amount_debit: Optional[float] = None
    balancing_type: Optional[str] = None
    contra_account_number: Optional[int] = None
    document_field2: Optional[str] = None
    due_date: Optional[str] = None
    due_days: Optional[int] = None
    has_dunning_block: bool = False
    kost1_cost_center_id: Optional[str] = None
    term_of_payment_id: Optional[int] = None
    # --- pre-existing, unconfirmed optional fields (kept, not contradicted) ---
    assessment_year: Optional[int] = None
    assigned_due_date: Optional[str] = None
    balance_type: Optional[str] = None
    # --- receivable-only, pre-existing (W1: zero real evidence either way) ---
    dunning_date1: Optional[str] = None
    dunning_date2: Optional[str] = None
    dunning_date3: Optional[str] = None


# Declaration order for the inferred-by-pattern XML shape (no direct real
# XML evidence for any of the 3 endpoints this model backs — both real
# captures were JSON content despite their `.xml` filenames, same quirk
# already noted for `fiscal_years`). `Id`/`Parent`/`membersToSerialize`
# preamble, then the remaining scalar fields in alphabetical PascalCase
# order, matching every confirmed real sample's convention.
OPEN_ITEM_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "account_number",
    "accounting_sequence_id",
    "amount_credit",
    "amount_debit",
    "amount_entered",
    "assessment_year",
    "assigned_due_date",
    "balance_type",
    "balancing_type",
    "contra_account_number",
    "currency_code",
    "date",
    "debit_credit_identifier",
    "document_field1",
    "document_field2",
    "due_date",
    "due_days",
    "dunning_date1",
    "dunning_date2",
    "dunning_date3",
    "evidence_type",
    "has_dunning_block",
    "has_interest_block",
    "is_cleared",
    "is_condensed",
    "kost1_cost_center_id",
    "open_balance_of_item",
    "open_item_number",
    "payment_method",
    "posting_description",
    "posting_record_number",
    "tax_rate",
    "term_of_payment_id",
]


@dataclass
class AccountingSequenceProcessed:
    """Accounting `accounting-sequence-read` (endpoint #4).

    Expanded to the real shape confirmed directly against
    `examples/accounting-sequences-processed.xml` (JSON content, 53
    records): `date_committed`/`inspection_status`/`mark_of_origin` are new
    real fields, all present on 100% of records — promoted to required
    along with `accounting_reason`/`accounting_sequence_id`/`date_from`/
    `date_to`/`description`/`is_committed`/`record_type` (all also 100%).
    `initials` stays optional (50/53 records, ~94%, genuinely sparse).
    `application_information` is a pre-existing, unconfirmed field (0
    occurrences in the real capture) — kept as-is, not contradicted."""

    id: str
    accounting_reason: str
    accounting_sequence_id: str
    date_committed: str
    date_from: str
    date_to: str
    description: str
    inspection_status: str
    is_committed: bool
    mark_of_origin: str
    record_type: str
    application_information: Optional[str] = None
    initials: Optional[str] = None


# Declaration order, inferred by pattern (no direct real XML evidence for
# this endpoint — same JSON-content-despite-`.xml`-filename quirk as
# `OpenItem`). `Id`/`Parent`/`membersToSerialize` preamble, then the
# remaining scalar fields in alphabetical PascalCase order.
ACCOUNTING_SEQUENCE_PROCESSED_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "accounting_reason",
    "accounting_sequence_id",
    "application_information",
    "date_committed",
    "date_from",
    "date_to",
    "description",
    "initials",
    "inspection_status",
    "is_committed",
    "mark_of_origin",
    "record_type",
]


@dataclass
class AccountingTransactionKey:
    """Accounting `accounting-transaction-keys` (endpoint #5).

    Expanded to the real shape confirmed directly against
    `examples/accounting-transaction-keys.xml` (JSON content, 465 records):
    `additional_function`/`caption`/`cases_related_to_goods_and_services`/
    `date_from`/`date_to`/`group` are new/promoted real fields, all present
    on **100%** of records (no optionality at all for this endpoint) —
    promoted alongside the pre-existing `id`/`is_tax_rate_selectable`/
    `number`/`tax_rate` (also 100%)."""

    id: str
    additional_function: str
    caption: str
    cases_related_to_goods_and_services: int
    date_from: str
    date_to: str
    group: str
    is_tax_rate_selectable: bool
    number: int
    tax_rate: float


# Declaration order, inferred by pattern (no direct real XML evidence for
# this endpoint). `Id`/`Parent`/`membersToSerialize` preamble, then the
# remaining scalar fields in alphabetical PascalCase order.
ACCOUNTING_TRANSACTION_KEY_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "additional_function",
    "caption",
    "cases_related_to_goods_and_services",
    "date_from",
    "date_to",
    "group",
    "is_tax_rate_selectable",
    "number",
    "tax_rate",
]


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


# Declaration order for the inferred-by-pattern XML shape (real-data
# reconciliation epic, W4 — both real captures returned empty `[]`, so
# there's zero real evidence beyond endpoint existence). `Id`/`Parent`/
# `membersToSerialize` preamble, then the remaining *scalar* fields in
# alphabetical PascalCase order. `assignment_criteria`
# (required nested object) and `posting_proposal_information` (nested list)
# are deliberately **excluded** — same precedent as `CostCenter`'s
# `cost_rates`/`properties`: no real evidence exists for a nested XML
# representation, so this mock doesn't invent one, they stay JSON-only.
POSTING_PROPOSAL_RULE_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "creation_date",
    "last_used_date",
    "uncertain_label",
]


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


# Declaration order for the inferred-by-pattern XML shape (real-data
# reconciliation epic, W4 — real evidence (`examples/terms-of-payment.xml`)
# confirms the JSON field shape exactly matches this model already, but
# provides no XML evidence). `Id`/`Parent`/`membersToSerialize` preamble,
# then the remaining *scalar* fields in alphabetical PascalCase order.
# `due_in_days`/`due_as_period` (nested optional objects) are deliberately
# **excluded** — same precedent as `PostingProposalRule` above and
# `CostCenter`'s `cost_rates`/`properties`: no real evidence exists for a
# nested XML representation, so this mock doesn't invent one.
TERM_OF_PAYMENT_FIELD_ORDER = [
    "id",
    "parent",
    "members_to_serialize",
    "caption",
    "cash_discount1_percentage",
    "cash_discount2_percentage",
    "due_type",
]


# --- DMS extension (extended-endpoints epic, Phase C) ---
#
# **No official spec exists for DMS** (confirmed via full-text grep of both
# bundled OpenAPI specs — zero "dms" matches). Unlike every other dataclass
# in this module, `Domain`/`Document` are a **self-designed schema**, built
# only from two one-line table rows in
# `examples/DATEV_Mock_Server_Reference.md`'s "DMS API" section plus
# `tests/test_dms.py`'s locked-in RED contract (see that file's module
# docstring and `odd/tasks/datev-mock-extended-endpoints.md`'s Phase C
# entry for the full reasoning). Field completeness here should not be
# assumed comparable to the spec-backed Phases A/B schemas above.


@dataclass
class Domain:
    """DMS `domain`/`folder`/`register` tree node.

    Modeled as a flat adjacency list (`parent_id` reference), not deep JSON
    nesting: `type` distinguishes the three tree levels named literally in
    the reference doc's description ("Domain/folder/register tree"),
    `parent_id` is present on every `folder`/`register` record (referencing
    another record's `id`) and **absent** (not `null`) on root
    `type == "domain"` records, per this epic's "optionality = field
    absence" convention.
    """

    id: str
    name: str
    type: str
    parent_id: Optional[str] = None


@dataclass
class Document:
    """DMS document metadata — per the reference doc's four named facets
    (amount, class, GUIDs, timestamps). `id` is a real GUID (the doc says
    "GUIDs" plural). `domain_id` ties a document to a node in the `domains`
    tree; `document_class` is a small invented enum (no real DATEV DMS
    document-class vocabulary exists anywhere in this repo's evidence)."""

    id: str
    name: str
    amount: float
    document_class: str
    domain_id: str
    created_at: str
    modified_at: str
