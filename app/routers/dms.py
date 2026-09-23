"""GET /datev/api/dms/v1/domains, documents — DMS (Document Management
System) mock endpoints.

New API area, added in the extended-endpoints epic, Phase C (see
`odd/tasks/datev-mock-extended-endpoints.md`). **No official DATEV OpenAPI
spec exists for DMS** — confirmed via a full-text grep of both bundled spec
files (zero "dms" matches). The schema served here is self-designed, built
only from two one-line table rows in
`examples/DATEV_Mock_Server_Reference.md`'s "DMS API" section and the
locked-in contract in `tests/test_dms.py` (see that file's module docstring
for the full reasoning). Field completeness should not be assumed
comparable to the spec-backed master-data/accounting endpoints.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Response

from app import data_store, overrides

router = APIRouter(tags=["dms"])

DOMAINS_ENDPOINT = "/datev/api/dms/v1/domains"
DOCUMENTS_ENDPOINT = "/datev/api/dms/v1/documents"


def _to_json(record: Any) -> dict[str, Any]:
    """Dataclass -> dict, dropping unset (`None`) optional fields.

    Matches this epic's convention of expressing "not set" as field absence
    rather than an explicit `null` (e.g. `Domain.parent_id` is absent, not
    `null`, on root `type == "domain"` records).
    """
    return {key: value for key, value in asdict(record).items() if value is not None}


@router.get(
    DOMAINS_ENDPOINT,
    summary="List DMS domains/folders/registers",
    description=(
        "Bare JSON array of the DMS domain/folder/register tree, flattened "
        "as an adjacency list (`parent_id` reference). Self-designed schema, "
        "no official spec exists for DMS."
    ),
)
def get_domains() -> list[dict[str, Any]]:
    override = overrides.get_active_override("dms.domains")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_domains()]


@router.get(
    DOCUMENTS_ENDPOINT,
    summary="List DMS documents",
    description=(
        "Bare JSON array of DMS document metadata (amount, class, GUIDs, "
        "timestamps). Self-designed schema, no official spec exists for DMS."
    ),
)
def get_documents() -> list[dict[str, Any]]:
    override = overrides.get_active_override("dms.documents")
    if override is not None:
        media_type = "application/xml" if override.content_type == "xml" else "application/json"
        return Response(content=override.content, media_type=media_type)

    return [_to_json(record) for record in data_store.list_documents()]
