"""GET /datev/api/master-data/v1/clients, addressees, banks — master-data
mock endpoints.

`clients` mirrors the real DATEV Sdd.Connect XML contract; `addressees` and
`banks` are the JSON-only Client Master Data API endpoints added in the
extended-endpoints epic, Phase A (see
`odd/tasks/datev-mock-extended-endpoints.md`).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response

from app import config, data_store, db, overrides
from app.json_serializers import serialize_master_data_clients_json
from app.models import Addressee, ClientResource, Employee
from app.write_models import AddresseeWrite, ClientResponsibility, ClientWrite, EmployeeWrite
from app.xml_serializers import serialize_client_resources

router = APIRouter(tags=["master-data"])

ENDPOINT = "/datev/api/master-data/v1/clients"
ADDRESSEES_ENDPOINT = "/datev/api/master-data/v1/addressees"
BANKS_ENDPOINT = "/datev/api/master-data/v1/banks"
# P3 (datev-mock-write-endpoints-and-observability.md, "Group B") -- new in
# this phase, no prior GET modeling. JSON-only, same "bare array" precedent
# as ADDRESSEES_ENDPOINT/BANKS_ENDPOINT above.
EMPLOYEES_ENDPOINT = "/datev/api/master-data/v1/employees"

# --- P2 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group A") -- `ClientResource`'s fields are PascalCase (matching the real
# XML element names), while `ClientWrite`'s fields are snake_case (matching
# the spec's own JSON body field names); every other Group A dataclass
# already uses snake_case 1:1 with its Pydantic write model, so only this
# one resource needs a translation table for `db.merge_with_stored`.
_CLIENT_RESOURCE_FIELD_MAP = {
    "id": "Id",
    "client_since": "ClientSince",
    "client_to": "ClientTo",
    "differing_name": "DifferingName",
    "legal_person_id": "LegalPersonId",
    "name": "Name",
    "natural_person_id": "NaturalPersonId",
    "note": "Note",
    "number": "Number",
    "status": "Status",
    "timestamp": "Timestamp",
    "type": "Type",
    "organization_id": "OrganizationId",
    "organization_name": "OrganizationName",
    "organization_number": "OrganizationNumber",
    "establishment_id": "EstablishmentId",
    "establishment_name": "EstablishmentName",
    "establishment_number": "EstablishmentNumber",
    "establishment_short_name": "EstablishmentShortName",
    "functional_area_id": "FunctionalAreaId",
    "functional_area_name": "FunctionalAreaName",
    "functional_area_short_name": "FunctionalAreaShortName",
}


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

    records = db.merge_with_stored(
        data_store.list_master_data(),
        "master_data.clients",
        ClientResource,
        id_field="Id",
        field_map=_CLIENT_RESOURCE_FIELD_MAP,
    )
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

    records = db.merge_with_stored(
        data_store.list_addressees(), "master_data.addressees", Addressee
    )
    return [_to_json(record) for record in records]


@router.get(
    ADDRESSEES_ENDPOINT + "/{addressee_id}",
    summary="Get a master-data addressee by id",
    description="Real lookup-by-id; 404 for an unknown addressee id.",
)
def get_addressee(addressee_id: str) -> dict[str, Any]:
    stored = db.get_record("master_data.addressees", addressee_id)
    if stored is not None:
        return stored
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


@router.get(
    EMPLOYEES_ENDPOINT,
    summary="List master-data employees",
    description=(
        "New in P3 (Group B) -- JSON-only bare array of Employee. No fake "
        "dataset exists for this brand-new resource (no `fake_data.py` "
        "generator); returns whatever's been POSTed/PUT so far, straight "
        "from app.db (same 'no merge needed, nothing to merge with' "
        "convention as the other new Group B GET handlers in "
        "app/routers/accounting.py)."
    ),
)
def get_employees() -> list[dict[str, Any]]:
    records = [
        db.record_to_dataclass(Employee, row) for row in db.list_records("master_data.employees")
    ]
    return [_to_json(record) for record in records]


@router.get(
    EMPLOYEES_ENDPOINT + "/{employee_id}",
    summary="Get a master-data employee by id",
    description="Real lookup-by-id; 404 for an unknown employee id.",
)
def get_employee(employee_id: str) -> dict[str, Any]:
    stored = db.get_record("master_data.employees", employee_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="employee not found")
    return _to_json(db.record_to_dataclass(Employee, stored))


# --- P2 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group A") --- same "validate via Pydantic, generate an id if absent,
# upsert, echo the stored record back" convention as
# `app/routers/accounting.py`'s write endpoints.


def _write_record(resource_type: str, body: Any, record_id: Optional[str] = None) -> dict[str, Any]:
    data = body.model_dump(exclude_none=True)
    resolved_id = record_id or data.get("id") or str(uuid.uuid4())
    data["id"] = resolved_id
    return db.upsert_record(resource_type, resolved_id, data)


# --- P2 write-side FK validation (architecture decision #6 + the feature
# doc's Appendix table) -- same `_validate_reference`/`merge_with_stored`-
# reuse convention as `app/routers/accounting.py`'s own P2 block; see that
# module's comment for the full rationale. Master data isn't scoped by
# client_id/fiscal_year_id (P1 finding: master-data write endpoints don't
# use that scoping either), so these candidate sets are global.


def _validate_reference(value: Optional[Any], candidates: set, field_name: str) -> None:
    if value is not None and value not in candidates:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: no matching record found for {value!r}",
        )


def _employee_ids() -> set[str]:
    merged = db.merge_with_stored([], "master_data.employees", Employee)
    return {record.id for record in merged}


def _client_resource_ids() -> set[str]:
    merged = db.merge_with_stored(
        data_store.list_master_data(),
        "master_data.clients",
        ClientResource,
        id_field="Id",
        field_map=_CLIENT_RESOURCE_FIELD_MAP,
    )
    return {record.Id for record in merged}


@router.post(ENDPOINT, status_code=201, summary="Create a master-data client")
def post_client(body: ClientWrite) -> dict[str, Any]:
    return _write_record("master_data.clients", body)


@router.put(ENDPOINT + "/{client_id}", summary="Update a master-data client by id")
def put_client(client_id: str, body: ClientWrite) -> dict[str, Any]:
    return _write_record("master_data.clients", body, record_id=client_id)


@router.put(
    ENDPOINT + "/{client_id}/responsibilities",
    summary="Replace a client's responsibilities",
    description=(
        "Full-replace semantics: the given array becomes the client's "
        "complete responsibilities list, replacing whatever was stored "
        "before. employee_id is validated against master-data.employees "
        "and client_id against master-data.clients (both global, P2); an "
        "unresolvable reference is rejected with 422."
    ),
)
def put_client_responsibilities(
    client_id: str, body: list[ClientResponsibility]
) -> list[dict[str, Any]]:
    employee_ids = _employee_ids()
    client_resource_ids = _client_resource_ids()
    for item in body:
        _validate_reference(item.employee_id, employee_ids, "employee_id")
        _validate_reference(item.client_id, client_resource_ids, "client_id")

    resource_type = "master_data.client_responsibilities"
    db.delete_records(resource_type, client_id=client_id)
    stored = []
    for item in body:
        data = item.model_dump(exclude_none=True)
        record_id = str(data["id"]) if "id" in data else str(uuid.uuid4())
        stored.append(db.upsert_record(resource_type, record_id, data, client_id=client_id))
    return stored


@router.post(ADDRESSEES_ENDPOINT, status_code=201, summary="Create a master-data addressee")
def post_addressee(body: AddresseeWrite) -> dict[str, Any]:
    return _write_record("master_data.addressees", body)


@router.put(ADDRESSEES_ENDPOINT + "/{addressee_id}", summary="Update a master-data addressee by id")
def put_addressee(addressee_id: str, body: AddresseeWrite) -> dict[str, Any]:
    return _write_record("master_data.addressees", body, record_id=addressee_id)


# --- P3 write endpoints (datev-mock-write-endpoints-and-observability.md,
# "Group B") --- same convention as every write endpoint above.


@router.post(EMPLOYEES_ENDPOINT, status_code=201, summary="Create a master-data employee")
def post_employee(body: EmployeeWrite) -> dict[str, Any]:
    return _write_record("master_data.employees", body)


@router.put(EMPLOYEES_ENDPOINT + "/{employee_id}", summary="Update a master-data employee by id")
def put_employee(employee_id: str, body: EmployeeWrite) -> dict[str, Any]:
    return _write_record("master_data.employees", body, record_id=employee_id)
