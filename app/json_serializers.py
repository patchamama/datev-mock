"""JSON rendering for the accounting `/clients` endpoint's JSON branch.

Only used when the caller sends `Accept: application/json`. The XML branch
(`xml_serializers.py`) is untouched by this module — kept deliberately
separate per the task's field-purity requirement.
"""
from __future__ import annotations

from app.models import Client


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
