"""GET /datev/api/master-data/v1/clients, addressees, banks — master-data
mock endpoints.

`clients` mirrors the real DATEV Sdd.Connect XML contract; `addressees` and
`banks` are the JSON-only Client Master Data API endpoints added in the
extended-endpoints epic, Phase A (see
`odd/tasks/datev-mock-extended-endpoints.md`).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app import data_store
from app.xml_serializers import serialize_client_resources

router = APIRouter(tags=["master-data"])

ENDPOINT = "/datev/api/master-data/v1/clients"
ADDRESSEES_ENDPOINT = "/datev/api/master-data/v1/addressees"
BANKS_ENDPOINT = "/datev/api/master-data/v1/banks"


def _to_json(record: Any) -> dict[str, Any]:
    """Dataclass -> dict, dropping unset (`None`) optional fields.

    Matches the spec's convention of expressing "not set" as field absence
    rather than an explicit `null` (neither Master Data spec uses OpenAPI
    `nullable` anywhere).
    """
    return {key: value for key, value in asdict(record).items() if value is not None}


@router.get(
    ENDPOINT,
    summary="List master-data clients",
    description="Returns ArrayOfClientResource XML, DATEV Sdd.Connect contract.",
)
def get_clients() -> Response:
    return Response(
        content=serialize_client_resources(data_store.list_master_data()),
        media_type="application/xml",
    )


@router.get(
    ADDRESSEES_ENDPOINT,
    summary="List master-data addressees",
    description="Bare JSON array of Addressee (top-level fields only; no expand support).",
)
def get_addressees() -> list[dict[str, Any]]:
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
    return [_to_json(record) for record in data_store.list_banks()]
