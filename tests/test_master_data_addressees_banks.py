"""RED-phase tests for the Master Data addressees and banks endpoints
(epic `datev-mock-extended-endpoints`, Phase A).

Ground truth: the compiled OpenAPI reference (`Client Master Data-1.6.0.json`,
resolved inline) written to the session scratchpad's
`datev-endpoint-specs.md` (sections #16 `GET /addressees`, #17
`GET /addressees/{addressee-id}`, #18 `GET /banks`), plus the cross-phase
decisions recorded in `odd/tasks/datev-mock-extended-endpoints.md`:

- All three endpoints are JSON-only, bare JSON array for the two list
  endpoints (never a pagination wrapper), single JSON object for the
  addressee-by-id endpoint.
- `Addressee` has no real OpenAPI polymorphism: it is one flat object with a
  `type` enum (`natural_person`|`legal_person`) plus parallel sibling
  properties gated only by description text, not a `oneOf`/`discriminator`.
- `GET /addressees/{addressee-id}` does a **real lookup by id** (the sole
  exception to this epic's "no path-param filtering" rule) and returns 404
  for an unknown id — an observed, documented behavior of the reference
  mock, not a guess.

These tests intentionally import `ADDRESSEES_ENDPOINT` / `BANKS_ENDPOINT`
directly from `app.routers.master_data`, which do not exist yet (only the
existing XML `clients` endpoint's `ENDPOINT` constant is defined there). This
import is expected to fail at collection time (`ImportError`) until the
GREEN-phase router work (task A2) adds these endpoints and their constants —
that failure is the correct RED signal for this task; do not add a
try/except around it to hide it.
"""
from __future__ import annotations

import uuid

from app.routers.master_data import ADDRESSEES_ENDPOINT, BANKS_ENDPOINT

MIN_ADDRESSEE_RECORDS = 5
MIN_BANK_RECORDS = 5

_ADDRESSEE_TYPES = {"natural_person", "legal_person"}
_ADDRESSEE_STATUSES = {"active", "inactive"}


def _get_addressees(client) -> list[dict]:
    response = client.get(ADDRESSEES_ENDPOINT)
    return response.json()


def _get_addressee_detail(client, addressee_id: str):
    return client.get(f"{ADDRESSEES_ENDPOINT}/{addressee_id}")


def _get_banks(client) -> list[dict]:
    response = client.get(BANKS_ENDPOINT)
    return response.json()


# --- GET /datev/api/master-data/v1/addressees ---


def test_addressees_returns_200(client):
    response = client.get(ADDRESSEES_ENDPOINT)
    assert response.status_code == 200


def test_addressees_content_type_is_json(client):
    response = client.get(ADDRESSEES_ENDPOINT)
    assert response.headers["content-type"].startswith("application/json")


def test_addressees_endpoint_requires_no_query_params(client):
    """Baseline check for the cross-phase "no select/filter/skip/top" decision:
    calling with no query params at all must work fine."""
    response = client.get(ADDRESSEES_ENDPOINT, params={})
    assert response.status_code == 200


def test_addressees_body_is_bare_array_with_minimum_records(client):
    records = _get_addressees(client)
    assert isinstance(records, list)
    assert len(records) >= MIN_ADDRESSEE_RECORDS, (
        f"expected at least {MIN_ADDRESSEE_RECORDS} addressee records, got {len(records)}"
    )


def test_addressee_record_has_core_top_level_fields(client):
    records = _get_addressees(client)
    assert records, "no addressee records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert record.get("type") in _ADDRESSEE_TYPES
        assert record.get("status") in _ADDRESSEE_STATUSES
        assert isinstance(record.get("timestamp"), str) and record["timestamp"].strip()


def test_addressee_dataset_contains_both_types(client):
    """Proves the fake dataset actually varies `type`, not just declares the
    enum — a dataset of a single type would let the parallel-field tests
    below pass vacuously."""
    records = _get_addressees(client)
    types_seen = {record.get("type") for record in records}
    assert types_seen == _ADDRESSEE_TYPES, (
        f"expected both natural_person and legal_person records, saw {types_seen}"
    )


def test_natural_person_addressees_have_representative_natural_person_fields(client):
    """Contract for GREEN: a `natural_person` record must carry at least its
    `firstname` and `current_surname` populated (the parallel `legal_person`
    fields need not be present/non-null on these records)."""
    records = _get_addressees(client)
    natural_person_records = [r for r in records if r.get("type") == "natural_person"]
    assert natural_person_records, "no natural_person addressee records returned"

    for record in natural_person_records:
        assert isinstance(record.get("firstname"), str) and record["firstname"].strip()
        assert isinstance(record.get("current_surname"), str) and record["current_surname"].strip()


def test_legal_person_addressees_have_representative_legal_person_fields(client):
    """Contract for GREEN: a `legal_person` record must carry at least its
    `current_company_name` populated (the parallel `natural_person` fields
    need not be present/non-null on these records)."""
    records = _get_addressees(client)
    legal_person_records = [r for r in records if r.get("type") == "legal_person"]
    assert legal_person_records, "no legal_person addressee records returned"

    for record in legal_person_records:
        assert (
            isinstance(record.get("current_company_name"), str)
            and record["current_company_name"].strip()
        )


# --- GET /datev/api/master-data/v1/addressees/{addressee-id} ---


def test_addressee_detail_valid_id_returns_200_single_object(client):
    records = _get_addressees(client)
    assert records, "no addressee records returned"
    known_id = records[0]["id"]

    response = _get_addressee_detail(client, known_id)
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, dict), "single-item response must be a JSON object, not an array"
    assert body.get("id") == known_id
    assert body.get("type") == records[0]["type"]


def test_addressee_detail_content_type_is_json(client):
    records = _get_addressees(client)
    assert records, "no addressee records returned"
    known_id = records[0]["id"]

    response = _get_addressee_detail(client, known_id)
    assert response.headers["content-type"].startswith("application/json")


def test_addressee_detail_unknown_id_returns_404(client):
    """Observed, documented real-mock behavior ("An arbitrary addressee ID
    returned 404") — this is the one endpoint in this epic that does real
    lookup-by-id filtering, deliberately tested here."""
    records = _get_addressees(client)
    known_ids = {record["id"] for record in records}

    arbitrary_id = str(uuid.uuid4())
    assert arbitrary_id not in known_ids  # sanity: not an accidental real id

    response = _get_addressee_detail(client, arbitrary_id)
    assert response.status_code == 404


# --- GET /datev/api/master-data/v1/banks ---


def test_banks_returns_200(client):
    response = client.get(BANKS_ENDPOINT)
    assert response.status_code == 200


def test_banks_content_type_is_json(client):
    response = client.get(BANKS_ENDPOINT)
    assert response.headers["content-type"].startswith("application/json")


def test_banks_endpoint_requires_no_query_params(client):
    response = client.get(BANKS_ENDPOINT, params={})
    assert response.status_code == 200


def test_banks_body_is_bare_array_with_minimum_records(client):
    records = _get_banks(client)
    assert isinstance(records, list)
    assert len(records) >= MIN_BANK_RECORDS, (
        f"expected at least {MIN_BANK_RECORDS} bank records, got {len(records)}"
    )


def test_bank_record_has_core_fields(client):
    records = _get_banks(client)
    assert records, "no bank records returned"

    for record in records:
        # `id` is spec-typed as a plain string (maxLength 6) — the spec's own
        # inline example inconsistently shows a bare number for one item, but
        # explicitly flags that as worth normalizing to string-always; this
        # mock always emits a string.
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("bic"), str) and record["bic"].strip()
        assert isinstance(record.get("country_code"), str) and record["country_code"].strip()
        assert isinstance(record.get("name"), str) and record["name"].strip()


def test_bank_bic_and_country_code_lengths_are_plausible(client):
    """Loose shape guard (not a strict pattern match) matching the spec's
    documented `bic` maxLength 11 and `country_code` maxLength 2, without
    hardcoding a specific fake BIC/country value."""
    records = _get_banks(client)
    assert records, "no bank records returned"

    for record in records:
        assert 1 <= len(record["bic"]) <= 11
        assert 1 <= len(record["country_code"]) <= 2
