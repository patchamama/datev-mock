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

from app.models import Addressee, Bank, Client, ClientResource, CompanyData

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


# Generated once at import time — stable for the lifetime of the process.
CLIENT_RESOURCES: list[ClientResource] = _generate_client_resources()
ACCOUNTING_CLIENTS: list[Client] = _generate_accounting_clients()
ADDRESSEES: list[Addressee] = _generate_addressees()
BANKS: list[Bank] = _generate_banks()
