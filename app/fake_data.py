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

from app.models import Client, ClientResource, CompanyData

random.seed(42)

# Small hardcoded pool of plausible fictitious German-sounding org names —
# no real DATEV client names are reused.
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
]

_CLIENT_TYPES = ["legal_person", "natural_person"]
_CLIENT_STATUSES = ["active", "inactive"]


def _fresh_guid() -> str:
    return str(uuid.uuid4())


def _random_timestamp() -> str:
    base = datetime(2015, 1, 1)
    offset_days = random.randint(0, 4000)
    offset_seconds = random.randint(0, 86399)
    ts = base + timedelta(days=offset_days, seconds=offset_seconds)
    return ts.isoformat(timespec="milliseconds")


def _generate_client_resources(count: int = 18) -> list[ClientResource]:
    records: list[ClientResource] = []
    names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    while len(names) < count:
        names.append(random.choice(_ORG_NAME_POOL))

    for index, number in enumerate(range(1, count + 1)):
        # Sparse population, matching the real sample: only a handful of
        # fields are ever populated, the rest stay i:nil.
        note = None if index % 3 != 0 else "VIP client"
        risk_assessment = None if index % 4 != 1 else "low"
        legal_person_id = _fresh_guid() if index % 2 == 0 else None
        client_since = _random_timestamp() if index % 5 == 0 else None

        records.append(
            ClientResource(
                Id=_fresh_guid(),
                LegalPersonId=legal_person_id,
                Name=names[index],
                Note=note,
                Number=number,
                RiskAssessment=risk_assessment,
                Status=random.choice(_CLIENT_STATUSES),
                Timestamp=_random_timestamp(),
                Type=random.choice(_CLIENT_TYPES),
                ClientSince=client_since,
            )
        )

    # Guarantee at least one explicit nil on Note or RiskAssessment even if
    # the modulo pattern above didn't happen to leave one (it always does
    # for count >= 3, but keep this as a hard guarantee for small counts).
    if not any(r.Note is None or r.RiskAssessment is None for r in records):
        records[0].Note = None
        records[0].RiskAssessment = None

    return records


def _generate_accounting_clients(count: int = 5) -> list[Client]:
    records: list[Client] = []
    names = random.sample(_ORG_NAME_POOL, k=min(count, len(_ORG_NAME_POOL)))
    while len(names) < count:
        names.append(random.choice(_ORG_NAME_POOL))

    for index in range(count):
        guid = _fresh_guid()
        number = 10000 + index
        # Only the first record carries populated company_data, mirroring
        # the documented JSON example (one populated, rest null/absent).
        company_data = (
            CompanyData(creditor_identifier=f"DE98ZZZ0999999{index:04d}")
            if index == 0
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


# Generated once at import time — stable for the lifetime of the process.
CLIENT_RESOURCES: list[ClientResource] = _generate_client_resources()
ACCOUNTING_CLIENTS: list[Client] = _generate_accounting_clients()
