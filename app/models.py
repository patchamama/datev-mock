"""Dataclasses backing the DATEV mock's three response shapes.

Field names intentionally mirror the real DATEV DataContractSerializer XML
element names (PascalCase for most, camelCase for `membersToSerialize`) so
that `xml_serializers.py` can render them directly without a translation
table. No real DATEV data is embedded here — only shapes.
"""
from __future__ import annotations

from dataclasses import dataclass
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
