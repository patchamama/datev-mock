"""RED-phase tests for the Accounting fiscal-year/cost-system structure
endpoints (epic `datev-mock-extended-endpoints`, Phase B, batch B1).

Covers 3 of the 15 target endpoints:
  - `GET /clients/{client-id}/fiscal-years` (compiled spec doc #1, client-level,
    not fiscal-year-scoped)
  - `GET .../fiscal-years/{fiscal-year-id}/cost-systems` (compiled spec doc #8)
  - `GET .../fiscal-years/{fiscal-year-id}/cost-systems/{cost-system-id}/cost-centers`
    (compiled spec doc #9)

Ground truth: the compiled OpenAPI reference written to the session
scratchpad's `datev-endpoint-specs.md`, plus the cross-phase decisions in
`odd/tasks/datev-mock-extended-endpoints.md`:

- All accounting list endpoints are JSON-only bare arrays (never a pagination
  wrapper).
- `{client-id}` / `{fiscal-year-id}` / `{cost-system-id}` path params are
  accepted but never filter the returned dataset — every call returns the
  same generic fake fixture regardless of the specific ids in the URL. This
  is explicitly tested below (`*_ignores_*_id_values`), not just documented.
- `cost-center.cost_rates[].valid_from`/`valid_to` are integer-encoded dates
  (e.g. `20161201`), not date-time strings — a spec quirk called out
  explicitly in the epic doc, tested below.

These tests intentionally import `FISCAL_YEARS_ENDPOINT` / `COST_SYSTEMS_ENDPOINT`
/ `COST_CENTERS_ENDPOINT` directly from `app.routers.accounting`, which do not
exist yet (only the existing XML `clients` endpoint's `ENDPOINT` constant is
defined there). This import is expected to fail at collection time
(`ImportError`) until the GREEN-phase router work (tasks B1/B2-GREEN) adds
these endpoints and their constants — that failure is the correct RED signal
for this task; do not add a try/except around it to hide it.
"""
from __future__ import annotations

import re
import uuid

from app.routers.accounting import (
    COST_CENTERS_ENDPOINT,
    COST_SYSTEMS_ENDPOINT,
    FISCAL_YEARS_ENDPOINT,
)

MIN_FISCAL_YEARS = 2
MIN_COST_SYSTEMS = 2
MIN_COST_CENTERS = 3

_LEGAL_FORM_VALUES = {
    "not_specified",
    "sole_proprietorship",
    "corporation",
    "cooperative",
    "partnership_under_the_german_civil_code",
    "limited_partnership_with_a_limited_liability_company_as_general_partner",
    "limited_partnership",
    "general_partnership",
    "association",
    "foundation",
    "public_corporation",
    "corporation_under_communal_budget_ordinance",
    "non_profit_corporation",
}
_TAXATION_METHOD_VALUES = {
    "not_specified",
    "taxation_based_on_value_of_services_rendered",
    "taxation_based_on_value_of_actual_receipts",
    "taxation_based_on_value_of_actual_receipts_input_tax_deduction_at_payment",
    "no_vat_calculation",
    "lump_sum",
}
_NATIONAL_RIGHT_VALUES = {"DE", "AT"}

_YYYYMMDD_RE = re.compile(r"^\d{8}$")


def _fresh_id() -> str:
    return str(uuid.uuid4())


def _get_fiscal_years(client, client_id: str = "any-client") -> list[dict]:
    response = client.get(FISCAL_YEARS_ENDPOINT.format(client_id=client_id))
    return response.json()


def _get_cost_systems(client, client_id: str = "any-client", fiscal_year_id: str = "any-fy") -> list[dict]:
    response = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=client_id, fiscal_year_id=fiscal_year_id)
    )
    return response.json()


def _get_cost_centers(
    client,
    client_id: str = "any-client",
    fiscal_year_id: str = "any-fy",
    cost_system_id: str = "any-cs",
) -> list[dict]:
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=client_id, fiscal_year_id=fiscal_year_id, cost_system_id=cost_system_id
        )
    )
    return response.json()


# --- GET .../clients/{client-id}/fiscal-years ---


def test_fiscal_years_returns_200_json_array_with_minimum_records(client):
    response = client.get(FISCAL_YEARS_ENDPOINT.format(client_id=_fresh_id()))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_FISCAL_YEARS, (
        f"expected at least {MIN_FISCAL_YEARS} fiscal-year records, got {len(records)}"
    )


def test_fiscal_year_record_has_core_fields(client):
    records = _get_fiscal_years(client)
    assert records, "no fiscal-year records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and _YYYYMMDD_RE.match(record["id"]), (
            "fiscal-year id must be a YYYYMMDD-formatted string"
        )
        assert isinstance(record.get("account_system"), int)
        assert isinstance(record.get("currency_code"), str) and 1 <= len(record["currency_code"]) <= 3
        assert record.get("legal_form") in _LEGAL_FORM_VALUES
        assert record.get("taxation_method") in _TAXATION_METHOD_VALUES
        assert record.get("national_right") in _NATIONAL_RIGHT_VALUES
        assert isinstance(record.get("is_locked"), bool)


def test_fiscal_years_ignores_client_id_value(client):
    """Locks in the cross-phase "no path-param filtering" decision as a
    tested contract: two arbitrary client ids must return the identical
    fake dataset."""
    first = _get_fiscal_years(client, client_id=_fresh_id())
    second = _get_fiscal_years(client, client_id=_fresh_id())
    assert first == second


# --- GET .../fiscal-years/{fiscal-year-id}/cost-systems ---


def test_cost_systems_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        COST_SYSTEMS_ENDPOINT.format(client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_COST_SYSTEMS, (
        f"expected at least {MIN_COST_SYSTEMS} cost-system records, got {len(records)}"
    )


def test_cost_system_record_has_core_fields(client):
    records = _get_cost_systems(client)
    assert records, "no cost-system records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and 1 <= len(record["id"]) <= 1
        assert isinstance(record.get("short_name"), str) and record["short_name"].strip()
        assert isinstance(record.get("is_activated_for_postings"), bool)
        # Spec types `number` as "number" (format "short") despite being an
        # integer-valued field in practice — see epic doc's quirk note.
        assert isinstance(record.get("number"), int)


def test_cost_systems_ignores_client_and_fiscal_year_id_values(client):
    first = _get_cost_systems(client, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    second = _get_cost_systems(client, client_id=_fresh_id(), fiscal_year_id=_fresh_id())
    assert first == second


# --- GET .../cost-systems/{cost-system-id}/cost-centers ---


def test_cost_centers_returns_200_json_array_with_minimum_records(client):
    response = client.get(
        COST_CENTERS_ENDPOINT.format(
            client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
        )
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    records = response.json()
    assert isinstance(records, list)
    assert len(records) >= MIN_COST_CENTERS, (
        f"expected at least {MIN_COST_CENTERS} cost-center records, got {len(records)}"
    )


def test_cost_center_record_has_core_fields(client):
    records = _get_cost_centers(client)
    assert records, "no cost-center records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("long_name"), str) and record["long_name"].strip()
        assert isinstance(record.get("short_name"), str) and record["short_name"].strip()
        assert isinstance(record.get("creation_date"), str) and record["creation_date"].strip()


def test_cost_center_cost_rates_use_integer_encoded_dates(client):
    """`cost_rates[].valid_from`/`valid_to` are documented as integer-encoded
    dates (e.g. `20161201`), not date-time strings — an explicit epic-doc
    quirk, tested here rather than just noted."""
    records = _get_cost_centers(client)
    records_with_rates = [r for r in records if r.get("cost_rates")]
    assert records_with_rates, "no cost-center record carries a populated cost_rates entry"

    for record in records_with_rates:
        for rate in record["cost_rates"]:
            assert isinstance(rate.get("valid_from"), int) and _YYYYMMDD_RE.match(str(rate["valid_from"]))
            assert isinstance(rate.get("valid_to"), int) and _YYYYMMDD_RE.match(str(rate["valid_to"]))
            assert isinstance(rate.get("rate"), (int, float))


def test_cost_centers_ignores_client_fiscal_year_and_cost_system_id_values(client):
    first = _get_cost_centers(
        client, client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
    )
    second = _get_cost_centers(
        client, client_id=_fresh_id(), fiscal_year_id=_fresh_id(), cost_system_id=_fresh_id()
    )
    assert first == second
