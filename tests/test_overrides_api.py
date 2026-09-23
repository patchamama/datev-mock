"""RED-phase tests for the `/admin/api/overrides*` HTTP contract
(`app/routers/admin.py`).

These endpoints don't exist yet. This file will fail either at collection
(`ModuleNotFoundError` for `app.overrides`, imported below for the isolation
fixture) or, once `app/overrides.py` exists but before V2-GREEN wires the
admin routes, as ordinary assertion failures (expected 200/422, got 404) —
both are valid RED signals per `odd/tasks/datev-mock-custom-overrides.md`.

## Contract under test (settled here, for the GREEN implementer)

- `POST /admin/api/overrides` — multipart upload, field name `file`.
  - Exactly one detected candidate -> `200`,
    `{"status": "matched", "endpoint": "<key>"}`; stored and enabled
    immediately.
  - Multiple candidates -> `200`,
    `{"status": "ambiguous", "candidates": ["<key>", ...], "pending_id": "<uuid>"}`;
    nothing becomes an active/listed override yet.
  - Zero candidates -> `422`, `{"status": "unrecognized"}`; nothing stored.
- `POST /admin/api/overrides/resolve` — body
  `{"pending_id": "...", "endpoint": "<key>"}` (key must be one of the
  candidates returned by the matching upload call) -> `200`; the pending
  content is assigned to `<key>` and enabled. Exact response body beyond
  the 200 status is intentionally left unspecified by the task doc, so
  it isn't asserted here — the resulting state is checked via a follow-up
  `GET /admin/api/overrides` instead.
- `GET /admin/api/overrides` -> `200`, JSON object keyed by endpoint key,
  each value carrying at least `filename`, `content_type`, `enabled`,
  `uploaded_at`.
- `PUT /admin/api/overrides/{key}` — body `{"enabled": bool}` -> `200`;
  toggles without deleting the stored override.
- `DELETE /admin/api/overrides/{key}` -> `200`; removes the override
  entirely.

## Test isolation

Mirrors `tests/test_admin_api.py`'s local, file-scoped autouse-fixture
pattern (not touching `tests/conftest.py`): overrides are process-lifetime,
in-memory state, so each test clears them via `app.overrides`'s test-only
`clear_all_overrides()` helper before and after every test.
"""
from __future__ import annotations

import json

import pytest

from app import overrides

OVERRIDES_ENDPOINT = "/admin/api/overrides"
RESOLVE_ENDPOINT = "/admin/api/overrides/resolve"


@pytest.fixture(autouse=True)
def _clear_overrides():
    overrides.clear_all_overrides()
    yield
    overrides.clear_all_overrides()


def _banks_json_bytes() -> bytes:
    return json.dumps(
        [
            {
                "id": "1",
                "bic": "GENODEF1M01",
                "bank_code": "12345678",
                "city": "Munich",
                "country_code": "DE",
                "name": "Testbank",
                "standard": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ]
    ).encode("utf-8")


def _creditor_debitor_json_bytes() -> bytes:
    return json.dumps(
        [
            {
                "id": "1",
                "account_number": 70000,
                "addressee_id": "addr-1",
                "business_partner_number": "70000",
                "legal_entity_type": "natural_person",
                "short_name": "Test",
            }
        ]
    ).encode("utf-8")


def test_upload_unambiguous_json_matches_and_enables_it(client):
    response = client.post(
        OVERRIDES_ENDPOINT,
        files={"file": ("banks.json", _banks_json_bytes(), "application/json")},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "matched", "endpoint": "master_data.banks"}

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert listing["master_data.banks"]["enabled"] is True


def test_upload_ambiguous_json_returns_candidates_and_pending_id(client):
    response = client.post(
        OVERRIDES_ENDPOINT,
        files={
            "file": (
                "creditor_or_debitor.json",
                _creditor_debitor_json_bytes(),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ambiguous"
    assert set(body["candidates"]) == {"accounting.creditors", "accounting.debitors"}
    assert "pending_id" in body

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert "accounting.creditors" not in listing
    assert "accounting.debitors" not in listing


def test_resolve_ambiguous_upload_assigns_and_enables_chosen_endpoint(client):
    upload = client.post(
        OVERRIDES_ENDPOINT,
        files={
            "file": (
                "creditor_or_debitor.json",
                _creditor_debitor_json_bytes(),
                "application/json",
            )
        },
    )
    pending_id = upload.json()["pending_id"]

    response = client.post(
        RESOLVE_ENDPOINT,
        json={"pending_id": pending_id, "endpoint": "accounting.creditors"},
    )
    assert response.status_code == 200

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert "accounting.creditors" in listing
    assert listing["accounting.creditors"]["enabled"] is True


def test_upload_unrecognizable_content_is_rejected_and_stores_nothing(client):
    response = client.post(
        OVERRIDES_ENDPOINT,
        files={"file": ("garbage.txt", b'{"foo": "bar"}', "application/json")},
    )

    assert response.status_code == 422
    assert response.json()["status"] == "unrecognized"

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert listing == {}


def test_put_override_disables_it_without_deleting(client):
    client.post(
        OVERRIDES_ENDPOINT,
        files={"file": ("banks.json", _banks_json_bytes(), "application/json")},
    )

    response = client.put(f"{OVERRIDES_ENDPOINT}/master_data.banks", json={"enabled": False})
    assert response.status_code == 200

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert "master_data.banks" in listing
    assert listing["master_data.banks"]["enabled"] is False


def test_delete_override_removes_it_from_listing(client):
    client.post(
        OVERRIDES_ENDPOINT,
        files={"file": ("banks.json", _banks_json_bytes(), "application/json")},
    )

    response = client.delete(f"{OVERRIDES_ENDPOINT}/master_data.banks")
    assert response.status_code == 200

    listing = client.get(OVERRIDES_ENDPOINT).json()
    assert "master_data.banks" not in listing
