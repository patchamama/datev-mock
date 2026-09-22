"""GET /datev/api/accounting/v1/clients — accounting mock endpoint.

Content-negotiated on a single port (58452): `Accept: application/json`
returns the documented JSON shape; `Accept: application/xml` or no explicit
preference keeps the existing real-traffic-capture XML shape (`ArrayOfClient`).
See "## Decisions" in `odd/tasks/datev-mock.md` for the rationale.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response

from app.fake_data import ACCOUNTING_CLIENTS
from app.json_serializers import serialize_clients_json
from app.xml_serializers import serialize_clients

router = APIRouter(tags=["accounting"])

ENDPOINT = "/datev/api/accounting/v1/clients"


@router.get(
    ENDPOINT,
    summary="List accounting clients",
    description=(
        "Returns ArrayOfClient XML by default (DATEV Irw.Connect.Accounting "
        "contract), or the documented JSON shape when Accept: application/json "
        "is sent."
    ),
)
def get_accounting_clients(request: Request) -> Response:
    accept = request.headers.get("accept", "")
    if "application/json" in accept.lower():
        payload = serialize_clients_json(ACCOUNTING_CLIENTS)
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(
        content=serialize_clients(ACCOUNTING_CLIENTS),
        media_type="application/xml",
    )
