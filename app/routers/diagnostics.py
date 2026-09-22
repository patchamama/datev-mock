"""GET /datev/api/diagnostics/v1/echo — diagnostics mock endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Response

from app.models import Echo
from app.xml_serializers import serialize_echo

router = APIRouter(tags=["diagnostics"])

ENDPOINT = "/datev/api/diagnostics/v1/echo"


@router.get(
    ENDPOINT,
    summary="Echo diagnostics probe",
    description="Returns a fresh echo message and GUID id, DATEV Echo XML contract.",
)
def get_echo() -> Response:
    now = datetime.now()
    echo = Echo(
        echo_message=f"echo at {now.strftime('%d.%m.%Y %H:%M:%S')}",
        id=str(uuid.uuid4()),
    )
    return Response(content=serialize_echo(echo), media_type="application/xml")
