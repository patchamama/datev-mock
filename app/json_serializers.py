"""JSON rendering for the accounting `/clients` endpoint's JSON branch.

Only used when the caller sends `Accept: application/json`. The XML branch
(`xml_serializers.py`) is untouched by this module — kept deliberately
separate per the task's field-purity requirement.
"""
from __future__ import annotations

from app.models import Client, ClientResource


def serialize_clients_json(records: list[Client]) -> list[dict]:
    """Render accounting clients per the documented DATEV JSON shape.

    `number` is a real integer, matching real captured evidence (a live
    installation capture in `examples/accounting-clients.xml`, JSON content
    despite the filename). The official docs' example, `"number": "47011"`
    (a string), was based on stale/inaccurate documentation and is not what
    a real installation actually returns — do not coerce to `str`.
    `company_data` is `null` for records without a populated creditor
    identifier, and an object with `creditor_identifier` for the ones that
    have one.
    """
    result: list[dict] = []
    for record in records:
        entry: dict = {
            "id": record.Id,
            "name": record.Name,
            "number": record.Number,
            "company_data": (
                {"creditor_identifier": record.company_data.creditor_identifier}
                if record.company_data is not None
                else None
            ),
        }
        result.append(entry)
    return result


def serialize_master_data_clients_json(records: list[ClientResource]) -> list[dict]:
    """Render master-data clients' JSON projection — a simplified variant of
    the full 42-field XML shape, not an independent schema (real-data
    reconciliation epic, W4).

    Real evidence (`examples/master-data-clients.xml`, JSON content despite
    the `.xml` filename, 100 records): the epic doc's own field table
    (derived from a compiled first-record summary) listed 7 always-present
    fields (`id`, `legal_person_id`, `name`, `number`, `status`, `timestamp`,
    `type`) but **missed 2 real optional fields** present on later records —
    `client_since` (14/100 records) and `client_to` (1/100 records),
    confirmed by counting occurrences across the full file, not just the
    first record. Both already exist on `ClientResource`
    (`ClientSince`/`ClientTo`) and are included here, omitted when unset.

    `number` confirmed a real unquoted JSON integer on all 100 sampled
    records (same precedent as `serialize_clients_json`'s W1 fix for
    `accounting.clients`) — not coerced to `str`.
    """
    result: list[dict] = []
    for record in records:
        entry: dict = {
            "id": record.Id,
            "legal_person_id": record.LegalPersonId,
            "name": record.Name,
            "number": record.Number,
            "status": record.Status,
            "timestamp": record.Timestamp,
            "type": record.Type,
            "client_since": record.ClientSince,
            "client_to": record.ClientTo,
        }
        result.append({key: value for key, value in entry.items() if value is not None})
    return result
