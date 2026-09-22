"""GET /datev/api/master-data/v1/clients — master-data mock endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Response

from app.fake_data import CLIENT_RESOURCES
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
        content=serialize_client_resources(CLIENT_RESOURCES),
        media_type="application/xml",
    )
