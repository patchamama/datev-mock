"""GET /datev/api/master-data/v1/clients — master-data mock endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Response

from app import data_store
from app.xml_serializers import serialize_client_resources

router = APIRouter(tags=["master-data"])

ENDPOINT = "/datev/api/master-data/v1/clients"


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
