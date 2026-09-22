"""Seeded synthetic dataset generation for the DATEV mock.

No real DATEV values are used — only the sparsity pattern and field shapes
observed in the real capture files (see task doc / agent instructions).
Deterministic via a fixed `random.seed`, computed once at module load so the
same dataset is served for the lifetime of the process (fresh only on
restart), matching how a stub/mock server is normally used.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from app.models import (
    Addressee,
    AccountingSequenceProcessed,
    AccountingTransactionKey,
    AssetStocktaking,
    AssignmentCriteria,
    Bank,
    Client,
    ClientResource,
    CompanyData,
    CostCenter,
    CostRate,
    CostSystem,
    Creditor,
    CreditorAccountingInformation,
    Debitor,
    DebitorAccountingInformation,
    Document,
    Domain,
    DueAsPeriod,
    DueDate,
    DueInDays,
    FiscalYear,
    GeneralLedgerAccount,
    GeneralLedgerAccountMinimal,
    GeneralLedgerAccountTaxRate,
    LegalPerson,
    NaturalPerson,
    OpenItem,
    Period,
    PostingProposalInformation,
    PostingProposalRule,
    TermOfPayment,
)

random.seed(42)

# Pool of plausible fictitious German-sounding organization names — varied
# legal-form suffixes, none resembling any real company. Used for
# `legal_person` records (and, historically, for all records before natural
# persons were differentiated).
_ORG_NAME_POOL = [
    "Musterhandel GmbH",
    "Nordlicht Consulting",
    "Rheinblick Bau AG",
    "Waldeck Steuerberatung",
    "Silberbach Logistik",
    "Kupferstadt Handwerk e.K.",
    "Feldmann & Partner",
    "Ostwind Vertrieb GmbH",
    "Birkental Service",
    "Lindenhof Verwaltung",
    "Talblick Handels KG",
    "Sonnenberg Consulting",
    "Grauwald Immobilien",
    "Eichenpark Logistik GmbH",
    "Moorsee Beratung",
    "Blumenau Textilien",
    "Steinbach Metallbau",
    "Wiesengrund e.V.",
    "Hafenblick Spedition",
    "Kirchheim Softwarehaus",
    "Amselfeld Consulting GmbH",
    "Brunnwiese Handwerk e.K.",
    "Dornrain Vertriebs KG",
    "Erlenhain Bau UG",
    "Falkenau Treuhand GmbH",
    "Granitberg Logistik AG",
    "Haselbach GbR",
    "Ilmtal Softwarehaus GmbH",
    "Jaspisfeld Beratung",
    "Kalkstein Service e.V.",
    "Lerchenwald Handel",
    "Marmorbrunn Consulting KG",
    "Nesselgrund Textilien GmbH",
    "Opalstein Spedition",
    "Quellental Verwaltung e.K.",
    "Rosenmoor Immobilien UG",
    "Schieferberg Metallbau GmbH",
    "Tannenblick GbR",
    "Ulmenhof Vertrieb",
    "Vogelsang Treuhand AG",
]

# Small hardcoded pool of fictitious German-style person full names, used
# only for `natural_person` records — never a real person.
_PERSON_NAME_POOL = [
    "Erika Musterfrau",
    "Jonas Vogel",
    "Mira Lehmann",
    "Tobias Brandt",
    "Lena Fuchs",
    "Felix Schuster",
    "Katrin Ebert",
    "Simon Adler",
    "Anja Winkler",
    "David Krämer",
    "Nadine Sommer",
    "Paul Reuter",
    "Sabine Moser",
    "Lukas Dietrich",
    "Julia Berger",
]

_CLIENT_TYPES = ["legal_person", "natural_person"]
# Status distribution weighted so "active" is a clear majority (~80%).
_STATUS_WEIGHTED_POOL = ["active"] * 4 + ["inactive"]


def _fresh_guid() -> str:
    return str(uuid.uuid4())


def _random_timestamp(start_year: int = 2015, end_year: int = 2025) -> str:
    base = datetime(start_year, 1, 1)
    end = datetime(end_year, 1, 1)
    offset_days = random.randint(0, max((end - base).days, 1))
    offset_seconds = random.randint(0, 86399)
    ts = base + timedelta(days=offset_days, seconds=offset_seconds)
    return ts.isoformat(timespec="milliseconds")


def _random_date_after(iso_timestamp: str) -> str:
    """Return a plausible later ISO timestamp than `iso_timestamp`."""
    start = datetime.fromisoformat(iso_timestamp)
    offset_days = random.randint(30, 1500)
    ts = start + timedelta(days=offset_days)
    return ts.isoformat(timespec="milliseconds")


def _generate_client_resources(count: int = 18) -> list[ClientResource]:
    records: list[ClientResource] = []
    org_names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    while len(org_names) < count:
        org_names.append(random.choice(_ORG_NAME_POOL))

    for index, number in enumerate(range(1, count + 1)):
        client_type = random.choice(_CLIENT_TYPES)

        # Differentiate the display name by type: natural persons get a
        # fictitious person's full name, legal persons keep the org pool.
        if client_type == "natural_person":
            name = random.choice(_PERSON_NAME_POOL)
        else:
            name = org_names[index]

        # Sparse population, matching the real sample: only a handful of
        # fields are ever populated, the rest stay i:nil.
        note = None if index % 3 != 0 else "VIP client"
        risk_assessment = None if index % 4 != 1 else "low"
        legal_person_id = _fresh_guid() if index % 2 == 0 else None
        client_since = _random_timestamp() if index % 5 == 0 else None

        # A few ended relationships: ClientTo populated (after ClientSince)
        # only when ClientSince itself is populated.
        client_to = None
        if client_since is not None and index % 10 == 0:
            client_to = _random_date_after(client_since)

        # A handful of legal_person records carry a populated organization
        # name field, distinct from the display Name (check app/models.py:
        # OrganizationName is the real field name).
        organization_name = None
        if client_type == "legal_person" and index % 7 == 0:
            organization_name = org_names[index]

        # IdentificationStatus mostly nil, populated on a couple of records.
        identification_status = "verified" if index in (2, 9, 15) else None

        records.append(
            ClientResource(
                Id=_fresh_guid(),
                LegalPersonId=legal_person_id,
                Name=name,
                Note=note,
                Number=number,
                OrganizationName=organization_name,
                RiskAssessment=risk_assessment,
                Status=random.choice(_STATUS_WEIGHTED_POOL),
                Timestamp=_random_timestamp(),
                Type=client_type,
                ClientSince=client_since,
                ClientTo=client_to,
                IdentificationStatus=identification_status,
            )
        )

    # Guarantee at least one explicit nil on Note or RiskAssessment even if
    # the modulo pattern above didn't happen to leave one (it always does
    # for count >= 3, but keep this as a hard guarantee for small counts).
    if not any(r.Note is None or r.RiskAssessment is None for r in records):
        records[0].Note = None
        records[0].RiskAssessment = None

    return records


def _generate_accounting_clients(count: int = 8) -> list[Client]:
    records: list[Client] = []
    names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    while len(names) < count:
        names.append(random.choice(_ORG_NAME_POOL))

    # A few (not just the first) records carry populated company_data,
    # mirroring the documented JSON example (some populated, some
    # null/absent). The rest stay None.
    populated_indices = {0, 2, 5} if count >= 6 else {0}

    for index in range(count):
        guid = _fresh_guid()
        number = 10000 + index
        company_data = (
            CompanyData(creditor_identifier=f"DE{10 + index:02d}ZZZ0999999{index:04d}")
            if index in populated_indices
            else None
        )
        records.append(
            Client(
                Id=guid,
                ClientGuid=guid,
                Name=names[index],
                Number=number,
                company_data=company_data,
            )
        )
    return records


# --- addressees / banks (Phase A of the extended-endpoints epic) ---

# Fictitious legal-form ids (6 chars, DATEV `current_legal_form_id` shape),
# invented — do not correspond to any real DATEV lookup value.
_LEGAL_FORM_ID_POOL = ["GMBH01", "AG0001", "KG0001", "UG0001", "EV0000"]

# Maps each _PERSON_NAME_POOL first name to its matching sex, so generated
# natural_person records don't pair a name with a mismatched sex value.
_FIRST_NAME_SEX = {
    "Erika": "female",
    "Jonas": "male",
    "Mira": "female",
    "Tobias": "male",
    "Lena": "female",
    "Felix": "male",
    "Katrin": "female",
    "Simon": "male",
    "Anja": "female",
    "David": "male",
    "Nadine": "female",
    "Paul": "male",
    "Sabine": "female",
    "Lukas": "male",
    "Julia": "female",
}


def _split_person_name(full_name: str) -> tuple[str, str]:
    firstname, _, surname = full_name.partition(" ")
    return firstname, surname


def _generate_addressees(count: int = 8) -> list[Addressee]:
    """Generate a mixed natural_person/legal_person dataset.

    Guarantees both types are present (indices 0/1 forced to opposite types,
    the rest random) so the served list never vacuously satisfies the
    "both types present" contract by chance alone.
    """
    records: list[Addressee] = []
    org_names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    person_names = random.sample(_PERSON_NAME_POOL, k=min(count, len(_PERSON_NAME_POOL)))

    for index in range(count):
        if index == 0:
            addressee_type = "natural_person"
        elif index == 1:
            addressee_type = "legal_person"
        else:
            addressee_type = random.choice(_CLIENT_TYPES)

        timestamp = _random_timestamp()
        eu_vat_country = "DE" if index % 3 == 0 else None

        if addressee_type == "natural_person":
            full_name = person_names[index % len(person_names)]
            firstname, surname = _split_person_name(full_name)
            records.append(
                Addressee(
                    id=_fresh_guid(),
                    type=addressee_type,
                    status=random.choice(_STATUS_WEIGHTED_POOL),
                    timestamp=timestamp,
                    eu_vat_id_country_code=eu_vat_country,
                    eu_vat_id_number=f"DE{100000000 + index}" if eu_vat_country else None,
                    current_short_name=firstname[:15],
                    surrogate_name=f"{surname}, {firstname}"[:50],
                    date_of_birth=_random_timestamp(1950, 2000)[:10],
                    etin=f"MUSTER{index:02d}A{index % 10}B",
                    firstname=firstname,
                    sex=_FIRST_NAME_SEX.get(firstname, "diverse"),
                    current_surname=surname,
                    tax_identification_number=str(10000000000 + index),
                )
            )
        else:
            company_name = org_names[index % len(org_names)]
            records.append(
                Addressee(
                    id=_fresh_guid(),
                    type=addressee_type,
                    status=random.choice(_STATUS_WEIGHTED_POOL),
                    timestamp=timestamp,
                    eu_vat_id_country_code=eu_vat_country,
                    eu_vat_id_number=f"DE{200000000 + index}" if eu_vat_country else None,
                    current_short_name=company_name.split(" ")[0][:15],
                    surrogate_name=company_name[:50],
                    current_company_name=company_name,
                    date_of_foundation=_random_timestamp(1970, 2020)[:10],
                    current_legal_form_id=_LEGAL_FORM_ID_POOL[index % len(_LEGAL_FORM_ID_POOL)],
                )
            )

    return records


# Fictitious bank pool — invented BIC/name/city combinations, none matching
# any real German (or other) bank's actual identifiers.
_BANK_POOL = [
    {"name": "Musterbank Nord eG", "bic": "MUSTDE1XXX", "city": "Hamburg", "country_code": "DE"},
    {"name": "Fiktivbank Süd AG", "bic": "FIKTDE2XXX", "city": "München", "country_code": "DE"},
    {"name": "Beispielkasse West", "bic": "BEISDE3X", "city": "Köln", "country_code": "DE"},
    {"name": "Probebank Ost eG", "bic": "PROBDE4XXX", "city": "Dresden", "country_code": "DE"},
    {"name": "Testfeld Sparkasse", "bic": "TESTDE5X", "city": "Stuttgart", "country_code": "DE"},
    {"name": "Musterland Bank AT", "bic": "MUSTAT2X", "city": "Wien", "country_code": "AT"},
    {"name": "Fiktivinstitut PL", "bic": "FIKTPL22", "city": "Warszawa", "country_code": "PL"},
    {"name": "Beispielbank CH", "bic": "BEISCH1X", "city": "Zürich", "country_code": "CH"},
]


def _generate_banks(count: int = 6) -> list[Bank]:
    records: list[Bank] = []
    pool = _BANK_POOL[: min(count, len(_BANK_POOL))]
    for index, entry in enumerate(pool):
        records.append(
            Bank(
                id=f"{index + 1:06d}",
                bank_code=str(10000000 + index * 111)[: (8 if entry["country_code"] == "DE" else 5)],
                bic=entry["bic"],
                city=entry["city"],
                country_code=entry["country_code"],
                name=entry["name"],
                standard=index % 3 != 0,
                timestamp=_random_timestamp()[:10],
            )
        )
    return records


# --- Accounting extension, Phase B batch B1 (extended-endpoints epic) ---
#
# Per the epic's cross-phase "no path-param filtering" decision, none of
# these datasets vary by client_id/fiscal_year_id/cost_system_id — routers
# always serve the same fixed fake dataset regardless of the URL. Minimum
# record counts follow the RED-imposed floors recorded in the task doc's B0
# progress entry (judgment calls, not spec-derived).

_LEGAL_FORM_VALUES = [
    "not_specified",
    "sole_proprietorship",
    "corporation",
    "cooperative",
    "partnership_under_the_german_civil_code",
    "limited_partnership_with_a_limited_liability_company_as_general_partner",
    "limited_partnership",
    "general_partnership",
    "association",
    "foundation",
    "public_corporation",
    "corporation_under_communal_budget_ordinance",
    "non_profit_corporation",
]
_TAXATION_METHOD_VALUES = [
    "not_specified",
    "taxation_based_on_value_of_services_rendered",
    "taxation_based_on_value_of_actual_receipts",
    "taxation_based_on_value_of_actual_receipts_input_tax_deduction_at_payment",
    "no_vat_calculation",
    "lump_sum",
]
_NATIONAL_RIGHT_VALUES = ["DE", "AT"]
_ACCOUNT_SYSTEM_VALUES = [3, 4, 4, 4, 49]  # DATEV SKR chart-of-accounts numbers (fictitious mix)

# Hardcoded lookup sets — the spec types these as plain integers, valid
# values only documented in free-text description, no OpenAPI enum. See
# `app/models.py::GeneralLedgerAccount` and the epic doc's explicit note.
_MAIN_FUNCTION_VALUES = [1, 2, 3, 4, 5, 6, 7]
_MAIN_FUNCTION_NUMBER_VALUES = [10, 11, 12, 20, 21, 25, 90, 91, 98]
_ADDITIONAL_FUNCTION_VALUES = [0, 1, 3, 8]

_LEGAL_ENTITY_TYPES = ["natural_person", "legal_person"]

_GL_ACCOUNT_CAPTIONS = [
    "Bank",
    "Kasse",
    "Forderungen aus Lieferungen und Leistungen",
    "Verbindlichkeiten aus Lieferungen und Leistungen",
    "Umsatzerlöse",
    "Wareneingang",
    "Abschreibungen auf Sachanlagen",
    "Sonstige betriebliche Aufwendungen",
    "Vorsteuer",
    "Umsatzsteuer",
]


def _generate_fiscal_years(count: int = 3) -> list[FiscalYear]:
    records: list[FiscalYear] = []
    for index in range(count):
        year = 2022 + index
        begin = f"{year}-01-01T00:00:00.000"
        end = f"{year}-12-31T23:59:59.000"
        records.append(
            FiscalYear(
                id=f"{year}0101",
                account_system=_ACCOUNT_SYSTEM_VALUES[index % len(_ACCOUNT_SYSTEM_VALUES)],
                currency_code="EUR",
                legal_form=_LEGAL_FORM_VALUES[index % len(_LEGAL_FORM_VALUES)],
                taxation_method=_TAXATION_METHOD_VALUES[index % len(_TAXATION_METHOD_VALUES)],
                national_right=_NATIONAL_RIGHT_VALUES[index % len(_NATIONAL_RIGHT_VALUES)],
                is_locked=index % 2 == 0,
                account_length=8,
                begin=begin,
                end=end,
                client_number=10000 + index,
                consultant_number=1000 + index,
                cost_length=8,
                is_invoice_date_check_on=index % 2 == 0,
                is_using_delivery_date=index % 3 == 0,
                is_using_receivable_type=index % 3 == 1,
                method_of_determining_net_income=(
                    "balance_sheet" if index % 2 == 0 else "cash_method_of_accounting"
                ),
            )
        )
    return records


def _generate_cost_systems(count: int = 3) -> list[CostSystem]:
    records: list[CostSystem] = []
    for index in range(count):
        records.append(
            CostSystem(
                id=str(index + 1),
                short_name=f"KoRe{index + 1}",
                is_activated_for_postings=index % 2 == 0,
                number=index + 1,
                cost_field=f"KOST{index + 1}",
            )
        )
    return records


def _generate_cost_centers(count: int = 4) -> list[CostCenter]:
    records: list[CostCenter] = []
    for index in range(count):
        creation_year = 2016 + index
        cost_rates = [
            CostRate(
                valid_from=int(f"{creation_year}1201"),
                valid_to=int(f"{creation_year + 1}1130"),
                rate=round(35.5 + index * 2.25, 2),
            )
        ] if index % 2 == 0 else []
        records.append(
            CostCenter(
                id=f"KST{index + 1:03d}",
                long_name=f"Kostenstelle {index + 1} Verwaltung",
                short_name=f"KST{index + 1}",
                creation_date=f"{creation_year}-01-15T00:00:00.000",
                cost_rates=cost_rates,
                date_last_modification=f"{creation_year}-06-01T00:00:00.000",
                responsible=_PERSON_NAME_POOL[index % len(_PERSON_NAME_POOL)],
            )
        )
    return records


def _generate_creditors(count: int = 4) -> list[Creditor]:
    """Forces both `legal_entity_type` values present (indices 0/1), same
    "not vacuous" pattern as `_generate_addressees`."""
    records: list[Creditor] = []
    org_names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    person_names = random.sample(_PERSON_NAME_POOL, k=min(count, len(_PERSON_NAME_POOL)))

    for index in range(count):
        if index == 0:
            entity_type = "natural_person"
        elif index == 1:
            entity_type = "legal_person"
        else:
            entity_type = random.choice(_LEGAL_ENTITY_TYPES)

        account_number = 70000 + index
        business_partner_number = str(account_number)
        addressee_id = _fresh_guid()

        natural_person = None
        legal_person = None
        if entity_type == "natural_person":
            full_name = person_names[index % len(person_names)]
            firstname, surname = _split_person_name(full_name)
            natural_person = NaturalPerson(firstname=firstname, surname=surname)
            short_name = f"{surname}"[:15]
        else:
            company_name = org_names[index % len(org_names)]
            legal_person = LegalPerson(legal_name=company_name)
            short_name = company_name.split(" ")[0][:15]

        records.append(
            Creditor(
                id=str(account_number),
                account_number=account_number,
                addressee_id=addressee_id,
                business_partner_number=business_partner_number,
                legal_entity_type=entity_type,
                short_name=short_name,
                natural_person=natural_person,
                legal_person=legal_person,
                accounting_information=CreditorAccountingInformation(
                    currency_management="payments_in_euro",
                    is_insolvent=False,
                    is_various_account=False,
                    language="german",
                    output_destination="print",
                    payment_medium="sepa_bank_transfer_with_one_invoice",
                ),
                is_business_partner_active=True,
                is_organization_business_partner=entity_type != "natural_person",
                caption=short_name,
            )
        )
    return records


def _generate_debitors(count: int = 4) -> list[Debitor]:
    """Debitor is structurally identical to creditor for the shared
    top-level fields (epic doc: GREEN must still populate
    `natural_person`/`legal_person` consistently, even though RED doesn't
    directly assert it for debitors)."""
    records: list[Debitor] = []
    org_names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    person_names = random.sample(_PERSON_NAME_POOL, k=min(count, len(_PERSON_NAME_POOL)))

    for index in range(count):
        if index == 0:
            entity_type = "natural_person"
        elif index == 1:
            entity_type = "legal_person"
        else:
            entity_type = random.choice(_LEGAL_ENTITY_TYPES)

        account_number = 10000 + index
        business_partner_number = str(account_number)
        addressee_id = _fresh_guid()

        natural_person = None
        legal_person = None
        if entity_type == "natural_person":
            full_name = person_names[index % len(person_names)]
            firstname, surname = _split_person_name(full_name)
            natural_person = NaturalPerson(firstname=firstname, surname=surname)
            short_name = f"{surname}"[:15]
        else:
            company_name = org_names[index % len(org_names)]
            legal_person = LegalPerson(legal_name=company_name)
            short_name = company_name.split(" ")[0][:15]

        records.append(
            Debitor(
                id=str(account_number),
                account_number=account_number,
                addressee_id=addressee_id,
                business_partner_number=business_partner_number,
                legal_entity_type=entity_type,
                short_name=short_name,
                natural_person=natural_person,
                legal_person=legal_person,
                accounting_information=DebitorAccountingInformation(
                    account_statement="account_statement_for_all_items",
                    credit_limit=50000 + index * 1000,
                    currency_management="payments_in_euro",
                    direct_debit="no_direct_debit_with_this_debitor",
                    dunning_procedure="first_and_second_dun",
                    interest_calculation="no_interest_calculated_for_this_debitor",
                    is_insolvent=False,
                    is_various_account=False,
                    language="german",
                    output_destination="print",
                ),
                is_business_partner_active=True,
                is_organization_business_partner=entity_type != "natural_person",
                caption=short_name,
            )
        )
    return records


def _generate_general_ledger_accounts(count: int = 6) -> list[GeneralLedgerAccount]:
    records: list[GeneralLedgerAccount] = []
    for index in range(count):
        records.append(
            GeneralLedgerAccount(
                id=str(1000 + index),
                account_number=1000 + index,
                caption=_GL_ACCOUNT_CAPTIONS[index % len(_GL_ACCOUNT_CAPTIONS)],
                main_function=_MAIN_FUNCTION_VALUES[index % len(_MAIN_FUNCTION_VALUES)],
                main_function_number=_MAIN_FUNCTION_NUMBER_VALUES[
                    index % len(_MAIN_FUNCTION_NUMBER_VALUES)
                ],
                additional_function=_ADDITIONAL_FUNCTION_VALUES[
                    index % len(_ADDITIONAL_FUNCTION_VALUES)
                ],
                function_description=_GL_ACCOUNT_CAPTIONS[index % len(_GL_ACCOUNT_CAPTIONS)],
                tax_rates=(
                    [GeneralLedgerAccountTaxRate(tax_rate=19.0, valid_from="2021-01-01T00:00:00.000")]
                    if index % 2 == 0
                    else []
                ),
            )
        )
    return records


# --- Accounting extension, Phase B batch B2 (extended-endpoints epic) ---
#
# Same "no path-param filtering" convention as batch B1's generators above.
# Minimum record counts follow the RED-imposed floors recorded in the task
# doc's B0 progress entry.

_EVIDENCE_TYPE_VALUES = [
    "invoice",
    "credit_note",
    "credit_note_by_revocation",
    "deposit",
    "payment",
    "cash_discount",
]
_DEBIT_CREDIT_IDENTIFIER_VALUES = ["S", "H"]
_DUNNING_LEVEL_VALUES = ["none", "level1", "level2", "level3"]


def _generate_open_items(count: int = 4, receivable: bool = False) -> list[OpenItem]:
    """Shared generator for `accounts-payable` (#6), `accounts-payable/condense`
    (#2) and `accounts-receivable/condense` (#3) — all three share the
    `OpenItem` schema per the compiled spec doc. `receivable=True` also
    populates the receivable-only `dunning_level` field on every record (a
    RED-imposed fake-data contract, see the epic doc's B0 progress entry)."""
    records: list[OpenItem] = []
    base_account = 10000 if receivable else 70000
    for index in range(count):
        debit_credit = _DEBIT_CREDIT_IDENTIFIER_VALUES[index % len(_DEBIT_CREDIT_IDENTIFIER_VALUES)]
        amount = round(100.0 + index * 37.5, 2)
        record = OpenItem(
            id=_fresh_guid(),
            account_number=base_account + index,
            amount_debit=amount if debit_credit == "S" else 0.0,
            amount_credit=amount if debit_credit == "H" else 0.0,
            amount_entered=amount,
            currency_code="EUR",
            evidence_type=_EVIDENCE_TYPE_VALUES[index % len(_EVIDENCE_TYPE_VALUES)],
            debit_credit_identifier=debit_credit,
            is_cleared=index % 3 == 0,
            open_balance_of_item=round(amount * 0.5, 2),
            accounting_sequence_id=str(1000 + index),
            date=f"2024-{(index % 9) + 1:02d}-15T00:00:00.000",
            due_date=f"2024-{((index % 2) + 10):02d}-15T00:00:00.000",
            due_days=30,
            posting_description=f"Beleg {index + 1}",
            tax_rate=19.0,
        )
        if receivable:
            record.dunning_level = _DUNNING_LEVEL_VALUES[index % len(_DUNNING_LEVEL_VALUES)]
            if index % 2 == 0:
                record.dunning_date1 = "2024-02-01T00:00:00.000"
        records.append(record)
    return records


_ACCOUNTING_REASON_VALUES = [
    "independent_from_accounting_reason",
    "reserved1",
    "reserved2",
    "commercial_law",
    "tax_law",
    "ifrs",
    "for_calculation",
]
_ACCOUNTING_SEQUENCE_RECORD_TYPE_VALUES = ["financial_accounting", "annual_financial_statements"]


def _generate_accounting_sequences_processed(count: int = 4) -> list[AccountingSequenceProcessed]:
    records: list[AccountingSequenceProcessed] = []
    for index in range(count):
        records.append(
            AccountingSequenceProcessed(
                id=str(2000 + index),
                accounting_sequence_id=str(3000 + index),
                description=f"Buchungsstapel {index + 1}",
                date_from=f"2024-{(index % 9) + 1:02d}-01T00:00:00.000",
                date_to=f"2024-{(index % 9) + 1:02d}-28T23:59:59.000",
                is_committed=index % 2 == 0,
                record_type=_ACCOUNTING_SEQUENCE_RECORD_TYPE_VALUES[
                    index % len(_ACCOUNTING_SEQUENCE_RECORD_TYPE_VALUES)
                ],
                accounting_reason=_ACCOUNTING_REASON_VALUES[index % len(_ACCOUNTING_REASON_VALUES)],
                initials="ABC",
            )
        )
    return records


_TRANSACTION_KEY_TAX_RATE_VALUES = [19.0, 7.0, 0.0, 16.0]


def _generate_accounting_transaction_keys(count: int = 4) -> list[AccountingTransactionKey]:
    records: list[AccountingTransactionKey] = []
    for index in range(count):
        records.append(
            AccountingTransactionKey(
                id=str(4000 + index),
                number=(index + 1) * 100,
                tax_rate=_TRANSACTION_KEY_TAX_RATE_VALUES[index % len(_TRANSACTION_KEY_TAX_RATE_VALUES)],
                is_tax_rate_selectable=index % 2 == 0,
                caption=f"Steuerschlüssel {index + 1}",
            )
        )
    return records


_STOCKTAKING_ACCOUNTING_REASON_VALUES = [50, 30, 40, 64, 11, 12]


def _generate_asset_stocktakings(count: int = 4) -> list[AssetStocktaking]:
    records: list[AssetStocktaking] = []
    for index in range(count):
        gl_account = (
            GeneralLedgerAccountMinimal(
                account_number=1000 + index,
                caption=_GL_ACCOUNT_CAPTIONS[index % len(_GL_ACCOUNT_CAPTIONS)],
            )
            if index % 2 == 0
            else None
        )
        records.append(
            AssetStocktaking(
                id=str(5000 + index),
                asset_number=6000 + index,
                inventory_number=f"INV-{index + 1:04d}",
                accounting_reason=_STOCKTAKING_ACCOUNTING_REASON_VALUES[
                    index % len(_STOCKTAKING_ACCOUNTING_REASON_VALUES)
                ],
                general_ledger_account=gl_account,
                inventory_name=f"Anlagegut {index + 1}",
                price=round(500.0 + index * 120, 2),
                quantity=1.0,
                stocktaking_date="2024-06-01T00:00:00.000",
                unit="Stück",
            )
        )
    return records


_ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES = [
    "own_input",
    "posting_description",
    "goods_and_services",
    "business_partner_name",
    "not_specified",
]
_ORIGIN_OF_POSTING_DESCRIPTION_OUTGOING_VALUES = _ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES + [
    "email",
    "transaction_key",
]


def _generate_posting_proposal_rules(count: int = 4, outgoing: bool = False) -> list[PostingProposalRule]:
    """Shared generator for `posting-proposal-rules-incoming-invoices` (#13)
    and `-outgoing-invoices` (#14) — identical shape per the compiled spec
    doc, only the allowed `origin_of_posting_description` enum differs."""
    origin_values = (
        _ORIGIN_OF_POSTING_DESCRIPTION_OUTGOING_VALUES if outgoing else _ORIGIN_OF_POSTING_DESCRIPTION_INCOMING_VALUES
    )
    id_base = 8000 if outgoing else 7000
    records: list[PostingProposalRule] = []
    for index in range(count):
        info_entries = [
            PostingProposalInformation(
                accounting_transaction_key=(index + 1) * 100,
                account_number=1000 + index,
                origin_of_posting_description=origin_values[index % len(origin_values)],
                posting_description=f"Buchungstext {index + 1}",
            )
        ]
        records.append(
            PostingProposalRule(
                id=str(id_base + index),
                uncertain_label=index % 3 == 0,
                assignment_criteria=AssignmentCriteria(
                    name=f"Kriterium {index + 1}",
                    tax_rate=19.0,
                ),
                posting_proposal_information=info_entries,
                creation_date="2024-01-01T00:00:00.000",
            )
        )
    return records


_RELATED_MONTH_VALUES = ["current_month", "next_month", "month_after_next"]


def _generate_terms_of_payment(count: int = 4) -> list[TermOfPayment]:
    """Guarantees both `due_type` variants are present (even indices get
    `due_in_days`, odd get `due_as_period`), same non-vacuous-mix pattern as
    `_generate_addressees`/`_generate_creditors`."""
    records: list[TermOfPayment] = []
    for index in range(count):
        if index % 2 == 0:
            due_type = "due_in_days"
            due_in_days = DueInDays(due_in_days=14 + index * 5, cash_discount1_days=7)
            due_as_period = None
        else:
            due_type = "due_as_period"
            due_in_days = None
            due_as_period = DueAsPeriod(
                period1=Period(
                    invoice_day_of_month=15,
                    due_date_net=DueDate(
                        related_month=_RELATED_MONTH_VALUES[index % len(_RELATED_MONTH_VALUES)],
                        day_of_month=10,
                    ),
                )
            )
        records.append(
            TermOfPayment(
                id=str(9000 + index),
                caption=f"Zahlungsbedingung {index + 1}",
                due_type=due_type,
                due_in_days=due_in_days,
                due_as_period=due_as_period,
                cash_discount1_percentage=2.0 if due_type == "due_in_days" else None,
            )
        )
    return records


# --- DMS extension (extended-endpoints epic, Phase C) ---
#
# **No official spec exists for DMS** — this fixed tree and the document
# fields below are a self-designed schema, not spec-derived. See
# `app/models.py::Domain`/`Document` and `tests/test_dms.py`'s module
# docstring for the full reasoning. Kept as a hand-authored fixed
# adjacency-list tree (not randomly generated) so the domain/folder/register
# hierarchy stays coherent and easy to reason about, unlike the flat
# unrelated-record lists generated elsewhere in this module.

_DMS_DOMAIN_TREE = [
    # (id, name, type, parent_id)
    ("DOM0001", "Unternehmen", "domain", None),
    ("DOM0002", "Belege", "folder", "DOM0001"),
    ("DOM0003", "Rechnungswesen", "folder", "DOM0001"),
    ("DOM0004", "Rechnungseingang", "register", "DOM0002"),
    ("DOM0005", "Rechnungsausgang", "register", "DOM0002"),
    ("DOM0006", "Kontoauszüge", "register", "DOM0003"),
]

_DOCUMENT_CLASS_VALUES = ["invoice", "receipt", "contract", "delivery_note"]

_DOCUMENT_NAME_POOL = [
    "Rechnung_2024_001.pdf",
    "Quittung_Buero.pdf",
    "Vertrag_Wartung.pdf",
    "Lieferschein_1042.pdf",
    "Rechnung_2024_002.pdf",
    "Quittung_Reise.pdf",
]


def _generate_domains() -> list[Domain]:
    """Fixed adjacency-list tree (domain -> folder -> register). Self-designed
    per the epic doc's Phase C note (no official DMS spec exists) — not
    randomly generated, since a coherent hand-authored tree is clearer than
    a randomized one for a resource this small."""
    return [
        Domain(id=node_id, name=name, type=node_type, parent_id=parent_id)
        for node_id, name, node_type, parent_id in _DMS_DOMAIN_TREE
    ]


def _generate_documents(count: int = 6) -> list[Document]:
    """Self-designed schema (epic doc Phase C note). `domain_id` cycles
    through `_DMS_DOMAIN_TREE`'s fixed node ids so every generated document
    references a real domain/folder/register node."""
    domain_ids = [node_id for node_id, _, _, _ in _DMS_DOMAIN_TREE]
    records: list[Document] = []
    for index in range(count):
        created = _random_timestamp()
        records.append(
            Document(
                id=_fresh_guid(),
                name=_DOCUMENT_NAME_POOL[index % len(_DOCUMENT_NAME_POOL)],
                amount=round(19.99 + index * 42.5, 2),
                document_class=_DOCUMENT_CLASS_VALUES[index % len(_DOCUMENT_CLASS_VALUES)],
                domain_id=domain_ids[index % len(domain_ids)],
                created_at=created,
                modified_at=_random_date_after(created),
            )
        )
    return records


# Generated once at import time — stable for the lifetime of the process.
CLIENT_RESOURCES: list[ClientResource] = _generate_client_resources()
ACCOUNTING_CLIENTS: list[Client] = _generate_accounting_clients()
ADDRESSEES: list[Addressee] = _generate_addressees()
BANKS: list[Bank] = _generate_banks()
FISCAL_YEARS: list[FiscalYear] = _generate_fiscal_years()
COST_SYSTEMS: list[CostSystem] = _generate_cost_systems()
COST_CENTERS: list[CostCenter] = _generate_cost_centers()
CREDITORS: list[Creditor] = _generate_creditors()
DEBITORS: list[Debitor] = _generate_debitors()
GENERAL_LEDGER_ACCOUNTS: list[GeneralLedgerAccount] = _generate_general_ledger_accounts()
ACCOUNTS_PAYABLE: list[OpenItem] = _generate_open_items(receivable=False)
ACCOUNTS_PAYABLE_CONDENSE: list[OpenItem] = _generate_open_items(receivable=False)
ACCOUNTS_RECEIVABLE_CONDENSE: list[OpenItem] = _generate_open_items(receivable=True)
ACCOUNTING_SEQUENCES_PROCESSED: list[AccountingSequenceProcessed] = _generate_accounting_sequences_processed()
ACCOUNTING_TRANSACTION_KEYS: list[AccountingTransactionKey] = _generate_accounting_transaction_keys()
ASSETS_STOCKTAKINGS: list[AssetStocktaking] = _generate_asset_stocktakings()
POSTING_PROPOSAL_RULES_INCOMING_INVOICES: list[PostingProposalRule] = _generate_posting_proposal_rules(
    outgoing=False
)
POSTING_PROPOSAL_RULES_OUTGOING_INVOICES: list[PostingProposalRule] = _generate_posting_proposal_rules(
    outgoing=True
)
TERMS_OF_PAYMENT: list[TermOfPayment] = _generate_terms_of_payment()
DOMAINS: list[Domain] = _generate_domains()
DOCUMENTS: list[Document] = _generate_documents()
