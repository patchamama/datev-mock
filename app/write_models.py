"""Pydantic request-body models for every write ("POST"/"PUT") endpoint
added in P2 of `odd/tasks/datev-mock-write-endpoints-and-observability.md`.

Kept in a dedicated module, separate from `app/models.py`, rather than
mixed into it: `app/models.py` is exclusively plain dataclasses backing the
*read* (GET) side's XML/JSON rendering, matching real DATEV element names
1:1 (see its own module docstring). Pydantic models have a different job —
runtime request-body validation, `required`/`optional` enforcement, and
Swagger UI "Try it out" bodies — and mixing the two idioms (dataclass
`@dataclass` vs Pydantic `BaseModel`) in one file would blur that
read/write separation this project already maintains elsewhere (e.g.
`json_serializers.py` vs `xml_serializers.py` staying separate per the
original task's own "field-purity requirement").

Field shapes below are taken directly from Appendix A of the feature doc
(itself resolved from DATEV's official OpenAPI 3.0.1 specs) — every field is
optional per its own `required` flag except where a field is explicitly
marked required. Nested `object`/`array` sub-fields with no established
shape elsewhere in this project (e.g. `Creditor`/`Debitor`'s
`addresses`/`banks`/`communications`, `CostCenter`'s `properties`,
`Addressee`'s `detail`/`addresses`/`communications`/`bank_accounts`/
`tax_offices`/`contact_persons`) are kept as permissive `dict`/`list[dict]`
passthroughs rather than fully modeled — consistent with this project's own
precedent for shape-unknown-but-present fields (e.g.
`CreditorAccountingInformation`'s "populated for shape-completeness only"
docstring) and proportionate to this phase's scope (Group A: the 7
resources already GET-modeled).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# --- shared nested shapes (`Creditor`/`Debitor`/`VariousAddress` family) ---


class NaturalPersonWrite(BaseModel):
    firstname: str
    surname: str
    date_of_birth: Optional[str] = None
    degree: Optional[str] = None
    name_prefix: Optional[str] = None
    title_of_nobility: Optional[str] = None


class LegalPersonWrite(BaseModel):
    legal_name: str
    enterprise_purpose: Optional[str] = None
    legal_form: Optional[str] = None


class NotSpecifiedPersonWrite(BaseModel):
    name: str


class CreditorAccountingInformationWrite(BaseModel):
    currency_management: Optional[str] = None
    is_insolvent: Optional[bool] = None
    is_various_account: Optional[bool] = None
    language: Optional[str] = None
    output_destination: Optional[str] = None
    payment_medium: Optional[str] = None
    term_of_payment_id: Optional[int] = None


class DebitorAccountingInformationWrite(BaseModel):
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


class _BusinessPartnerWriteBase(BaseModel):
    """Shared body shape for `debitors`/`creditors` -- POST create, PUT list
    (`merge-patch+json`), PUT by id all use the same shape per Appendix A."""

    id: Optional[str] = None
    account_number: Optional[int] = None
    addressee_id: Optional[str] = None
    alternative_search_name: Optional[str] = None
    business_partner_number: Optional[str] = None
    business_partner_relation_id: Optional[str] = None
    caption: Optional[str] = None
    complimentary_close: Optional[str] = None
    correspondence_title: Optional[str] = None
    date_last_modification: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    is_business_partner_active: Optional[bool] = None
    is_organization_business_partner: Optional[bool] = None
    legal_entity_type: Optional[str] = None
    salutation: Optional[str] = None
    short_name: Optional[str] = None
    third_party_number: Optional[str] = None
    natural_person: Optional[NaturalPersonWrite] = None
    legal_person: Optional[LegalPersonWrite] = None
    not_specified_person: Optional[NotSpecifiedPersonWrite] = None
    addresses: Optional[list[dict]] = None
    communications: Optional[list[dict]] = None
    banks: Optional[list[dict]] = None


class DebitorWrite(_BusinessPartnerWriteBase):
    accounting_information: Optional[DebitorAccountingInformationWrite] = None


class CreditorWrite(_BusinessPartnerWriteBase):
    accounting_information: Optional[CreditorAccountingInformationWrite] = None


# --- terms-of-payment ---


class DueDateWrite(BaseModel):
    related_month: str
    day_of_month: int


class PeriodWrite(BaseModel):
    invoice_day_of_month: int
    due_date_net: DueDateWrite
    due_date_cash_discount1: Optional[DueDateWrite] = None
    due_date_cash_discount2: Optional[DueDateWrite] = None


class DueInDaysWrite(BaseModel):
    due_in_days: int
    cash_discount1_days: Optional[int] = None
    cash_discount2_days: Optional[int] = None


class DueAsPeriodWrite(BaseModel):
    period1: PeriodWrite
    period2: Optional[PeriodWrite] = None
    period3: Optional[PeriodWrite] = None


class TermOfPaymentWrite(BaseModel):
    id: Optional[str] = None
    caption: str
    due_type: Optional[str] = None
    cash_discount1_percentage: Optional[float] = None
    cash_discount2_percentage: Optional[float] = None
    due_in_days: Optional[DueInDaysWrite] = None
    due_as_period: Optional[DueAsPeriodWrite] = None


# --- asset stocktaking ---


class GeneralLedgerAccountMinimalWrite(BaseModel):
    account_number: int
    caption: str


class AssetStocktakingWrite(BaseModel):
    id: Optional[str] = None
    asset_number: int
    inventory_number: str
    accounting_reason: Optional[int] = None
    general_ledger_account: Optional[GeneralLedgerAccountMinimalWrite] = None
    inventory_name: Optional[str] = None
    acquisition_date: Optional[str] = None
    economic_lifetime: Optional[int] = None
    kost1_cost_center_id: Optional[str] = None
    branch: Optional[int] = None
    order_date: Optional[str] = None
    origin_type: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    stocktaking_date: Optional[str] = None
    unit: Optional[str] = None
    farmland_number: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    contract_number: Optional[str] = None
    type_of_use: Optional[str] = None
    condition: Optional[str] = None
    isin: Optional[str] = None
    explanation_of_depreciation: Optional[str] = None


# --- cost centers ---


class CostRateWrite(BaseModel):
    valid_from: int
    valid_to: int
    rate: float


class CostCenterWrite(BaseModel):
    id: Optional[str] = None
    properties: Optional[list[dict]] = None
    cost_rates: Optional[list[CostRateWrite]] = None
    creation_date: Optional[str] = None
    date_last_modification: Optional[str] = None
    email: Optional[str] = None
    long_name: Optional[str] = None
    short_name: Optional[str] = None
    note: Optional[str] = None
    postable_from: Optional[str] = None
    postable_to: Optional[str] = None
    reference_value: Optional[str] = None
    responsible: Optional[str] = None


# --- master-data clients ---


class ClientWrite(BaseModel):
    id: Optional[str] = None
    client_since: Optional[str] = None
    client_to: Optional[str] = None
    differing_name: Optional[str] = None
    legal_person_id: Optional[str] = None
    name: str
    natural_person_id: Optional[str] = None
    note: Optional[str] = None
    number: int
    status: Optional[str] = None
    timestamp: Optional[str] = None
    type: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    organization_number: Optional[str] = None
    establishment_id: Optional[str] = None
    establishment_name: Optional[str] = None
    establishment_number: Optional[str] = None
    establishment_short_name: Optional[str] = None
    functional_area_id: Optional[str] = None
    functional_area_name: Optional[str] = None
    functional_area_short_name: Optional[str] = None


class ClientResponsibility(BaseModel):
    """`PUT /master-data/v1/clients/{client_id}/responsibilities` array-body
    item. References `employee_id`, which isn't a real resource until P3's
    `employees` — same "mock doesn't enforce relational integrity beyond
    shape" philosophy already established project-wide: not validated to
    exist, just stored as sent."""

    id: Optional[int] = None
    area_of_responsibility_id: Optional[str] = None
    area_of_responsibility_name: Optional[str] = None
    employee_id: Optional[str] = None
    employee_display_name: Optional[str] = None
    employee_number: Optional[int] = None
    employee_status: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_number: Optional[int] = None
    client_status: Optional[str] = None


# --- master-data addressees ---


class AddresseeWrite(BaseModel):
    """Per Appendix A: matches `Addressee` for the historical-array fields
    (already modeled read-side), plus several write-only fields the GET
    side never returns without `expand` support this mock doesn't
    implement (`detail`/`addresses`/`communications`/`bank_accounts`/
    `tax_offices`/`contact_persons`) -- persisted with full fidelity in
    SQLite, but not surfaced by the merged GET response (see
    `app/db.py::record_to_dataclass`'s "keys with no matching dataclass
    field are dropped" behavior).

    `detail` resolved directly against the bundled spec
    (`Client Master Data-1.6.0.json`, `#/components/schemas/Detail`) during
    this phase: a real ~70-field object (name/date/historical-value arrays
    for birth data, classification-of-economic-activities codes, register
    court info, etc.). Modeling every one of those as its own Pydantic
    class would be a large scope expansion for a phase whose stated focus
    is the 7 already-GET-modeled resources; kept as a permissive `dict`
    passthrough instead (same "shape-unknown-but-present" precedent as
    `CreditorAccountingInformationWrite` above) -- still fully validated as
    *an object*, still fully persisted and visible in the admin UI's
    "Stored records" JSON preview, just not broken down field-by-field.
    """

    id: Optional[str] = None
    eu_vat_id_country_code: Optional[str] = None
    eu_vat_id_number: Optional[str] = None
    short_names: Optional[list[dict]] = None
    current_short_name: Optional[str] = None
    status: Optional[str] = None
    surrogate_name: Optional[str] = None
    timestamp: Optional[str] = None
    type: str
    date_of_birth: Optional[str] = None
    etin: Optional[str] = None
    firstname: Optional[str] = None
    sex: Optional[str] = None
    surnames: Optional[list[dict]] = None
    current_surname: Optional[str] = None
    tax_identification_number: Optional[str] = None
    company_names: Optional[list[dict]] = None
    current_company_name: Optional[str] = None
    date_of_foundation: Optional[str] = None
    legal_form_ids: Optional[list[dict]] = None
    current_legal_form_id: Optional[str] = None
    detail: Optional[dict[str, Any]] = None
    addresses: Optional[list[dict]] = None
    communications: Optional[list[dict]] = None
    bank_accounts: Optional[list[dict]] = None
    tax_offices: Optional[list[dict]] = None
    contact_persons: Optional[list[dict]] = None
