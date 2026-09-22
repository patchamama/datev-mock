"""GET /datev/api/accounting/v1/clients — accounting mock endpoint.

Content-negotiated on a single port (58452), with three explicit states:
  - `Accept` explicitly contains `application/json` (and not
    `application/xml`) -> JSON, always.
  - `Accept` explicitly contains `application/xml` (and not
    `application/json`) -> XML, always.
  - Anything else (missing header, `*/*`, unrecognized, or contains both) ->
    ambiguous, so the live `default_accounting_format` setting (read fresh
    from `app.config` on every request) decides.
See "## Decisions" in `odd/tasks/datev-mock.md` for the original XML/JSON
shape rationale, and `odd/tasks/datev-mock-settings.md` for the live-setting
addition.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response

from app import config, data_store
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
        "is sent. When the Accept header doesn't unambiguously request one "
        "format or the other, the live default_accounting_format setting decides."
    ),
)
def get_accounting_clients(request: Request) -> Response:
    accept = request.headers.get("accept", "").lower()
    wants_json = "application/json" in accept
    wants_xml = "application/xml" in accept

    if wants_json and not wants_xml:
        response_format = "json"
    elif wants_xml and not wants_json:
        response_format = "xml"
    else:
        response_format = config.load_settings().default_accounting_format

    records = data_store.list_accounting_clients()

    if response_format == "json":
        payload = serialize_clients_json(records)
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(content=serialize_clients(records), media_type="application/xml")
