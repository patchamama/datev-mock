"""GET /datev/api/master-data/v1/clients, addressees, banks — master-data
mock endpoints.

`clients` mirrors the real DATEV Sdd.Connect XML contract; `addressees` and
`banks` are the JSON-only Client Master Data API endpoints added in the
extended-endpoints epic, Phase A (see
`odd/tasks/datev-mock-extended-endpoints.md`).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app import config, data_store, overrides
from app.json_serializers import serialize_master_data_clients_json
from app.xml_serializers import serialize_client_resources

router = APIRouter(tags=["master-data"])

ENDPOINT = "/datev/api/master-data/v1/clients"
ADDRESSEES_ENDPOINT = "/datev/api/master-data/v1/addressees"
BANKS_ENDPOINT = "/datev/api/master-data/v1/banks"


def _strip_none(value: Any) -> Any:
    """Recursively drop `None`-valued keys/entries, matching the spec's
    convention of expressing "not set" as field absence (neither Master Data
    spec uses OpenAPI `nullable` anywhere). Needed (not just a shallow
    top-level filter) since `Addressee`'s historical-array fields
    (`company_names`/`short_names`/`legal_form_ids`/`surnames`, real-data
    reconciliation epic W4) nest `HistoricalValue` objects whose own
    `valid_from` field is `None` on the majority of entries — real evidence
    (`examples/addressees.xml`) shows that absent as a missing key, not an
    explicit `null`."""
    if isinstance(value, dict):
        return {key: _strip_none(val) for key, val in value.items() if val is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value]
    return value


def _to_json(record: Any) -> dict[str, Any]:
    """Dataclass -> dict, dropping unset (`None`) optional fields, recursively."""
    return _strip_none(asdict(record))


# --- Real-data reconciliation epic, W4 batch C ---
#
# XML/JSON content negotiation for `master_data.clients` — same 3-state
# mechanism `accounting.clients`/the accounting sub-resources already use
# (`Accept: application/json` explicit -> JSON; `Accept: application/xml`
# explicit or ambiguous/missing -> the live `default_accounting_format`
# setting). No separate "default master-data format" setting exists, and the
# epic doc's cross-cutting decision calls this "the same" negotiation this
# mock already has for `accounting.clients` — reusing that one live setting
# here is the natural reading, not a new inferred setting.


def _negotiate_format(request: Request) -> str:
    accept = request.headers.get("accept", "").lower()
    wants_json = "application/json" in accept
    wants_xml = "application/xml" in accept

    if wants_json and not wants_xml:
        return "json"
    if wants_xml and not wants_json:
        return "xml"
    return config.load_settings().default_accounting_format


@router.get(
    ENDPOINT,
    summary="List master-data clients",
    description=(
        "Returns ArrayOfClientResource XML by default (DATEV Sdd.Connect "
        "contract), or a simplified 9-field JSON projection when "
        "Accept: application/json is sent (real evidence: "
        "examples/master-data-clients.xml). When the Accept header doesn't "
        "unambiguously request one format or the other, the live "
        "default_accounting_format setting decides."
    ),
)
def get_clients(request: Request) -> Response:
    override = overrides.get_active_override("master_data.clients")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    records = data_store.list_master_data()
    if _negotiate_format(request) == "json":
        payload = serialize_master_data_clients_json(records)
        return Response(content=json.dumps(payload), media_type="application/json")

    return Response(
        content=serialize_client_resources(records),
        media_type="application/xml",
    )


@router.get(
    ADDRESSEES_ENDPOINT,
    summary="List master-data addressees",
    description="Bare JSON array of Addressee (top-level fields only; no expand support).",
)
def get_addressees() -> list[dict[str, Any]]:
    override = overrides.get_active_override("master_data.addressees")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_addressees()]


@router.get(
    ADDRESSEES_ENDPOINT + "/{addressee_id}",
    summary="Get a master-data addressee by id",
    description="Real lookup-by-id; 404 for an unknown addressee id.",
)
def get_addressee(addressee_id: str) -> dict[str, Any]:
    record = data_store.get_addressee(addressee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="addressee not found")
    return _to_json(record)


@router.get(
    BANKS_ENDPOINT,
    summary="List master-data banks",
    description="Bare JSON array of Bank.",
)
def get_banks() -> list[dict[str, Any]]:
    override = overrides.get_active_override("master_data.banks")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_banks()]
