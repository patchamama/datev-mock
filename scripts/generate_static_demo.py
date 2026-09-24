"""Generate the static, read-only demo snapshot published to GitHub Pages.

Uses FastAPI's `TestClient` in-process (no live server needed) to call
every Group-A GET endpoint -- the ones with real fake data, see
`odd/tasks/datev-mock-static-demo-gh-pages.md` decision #3 -- for a small,
fixed set of demo ids (decision #1), and writes each response body
verbatim under `static-demo/data/`, mirroring the real URL path so the
relationship between a demo file and its real endpoint is obvious. Group B
routes (cost-center-properties, cost-sequences, cost-accounting-records,
various-addresses) are deliberately excluded -- they only ever reflect
what's been written via SQLite, so a fresh static export would always show
an empty array.

Both JSON (`Accept: application/json`) and XML (default, no `Accept`
header) are captured per resource, except for the handful of endpoints
that never had XML content negotiation in the first place (master-data
addressees/banks/employees, both DMS routes) -- those are JSON-only in the
live app too, so no `.xml` file is written for them (writing JSON content
under a `.xml` extension would misrepresent the real endpoint).

Idempotent: clears `static-demo/data/` at the start of every run, so
re-running cleanly overwrites (no leftover stale files from a prior demo-id
scheme). Also writes `static-demo/data/manifest.json`, the flat catalog the
static frontend (`static-demo/index.html`) fetches to build its UI.

Re-run whenever the underlying fake-data generation changes:

    .venv/Scripts/python scripts/generate_static_demo.py   (Windows)
    .venv/bin/python scripts/generate_static_demo.py        (Linux/macOS)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    # Allows running this script directly (`python scripts/generate_static_demo.py`)
    # from any cwd -- `app` is only importable once the repo root is on sys.path.
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# --- Fixed demo id set (architecture decision #1) ---
DEMO_CLIENTS = ["demo-client-1", "demo-client-2"]
DEMO_FISCAL_YEARS = ["demo-fy-2024", "demo-fy-2025"]
DEMO_COST_SYSTEM = "demo-cost-system-1"

_DATA_DIR = _REPO_ROOT / "static-demo" / "data"

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class EndpointSpec:
    resource_name: str
    path_template: str


# --- Fiscal-year-scoped Group-A GET routes (decision #3) ---
#
# Path templates match app/routers/accounting.py's own constants verbatim.
# `client_id`/`fiscal_year_id`/`cost_system_id` placeholders are filled from
# the demo id set above; which placeholders a template actually contains
# determines its manifest scope (see `_scope_for`) and whether it collapses
# to fewer generated files (e.g. "fiscal years" only varies by client_id).
_FISCAL_YEAR_PREFIX = "/datev/api/accounting/v1/clients/{client_id}/fiscal-years/{fiscal_year_id}"

SCOPED_ENDPOINTS = [
    EndpointSpec("Fiscal years", "/datev/api/accounting/v1/clients/{client_id}/fiscal-years"),
    EndpointSpec("Cost systems", f"{_FISCAL_YEAR_PREFIX}/cost-systems"),
    EndpointSpec(
        "Cost centers", f"{_FISCAL_YEAR_PREFIX}/cost-systems/{{cost_system_id}}/cost-centers"
    ),
    EndpointSpec("Creditors", f"{_FISCAL_YEAR_PREFIX}/creditors"),
    EndpointSpec("Debitors", f"{_FISCAL_YEAR_PREFIX}/debitors"),
    EndpointSpec("General ledger accounts", f"{_FISCAL_YEAR_PREFIX}/general-ledger-accounts"),
    EndpointSpec("Accounts payable", f"{_FISCAL_YEAR_PREFIX}/accounts-payable"),
    EndpointSpec(
        "Accounts payable (condensed)", f"{_FISCAL_YEAR_PREFIX}/accounts-payable/condense"
    ),
    EndpointSpec(
        "Accounts receivable (condensed)", f"{_FISCAL_YEAR_PREFIX}/accounts-receivable/condense"
    ),
    EndpointSpec(
        "Processed accounting sequences",
        f"{_FISCAL_YEAR_PREFIX}/accounting-sequences-processed",
    ),
    EndpointSpec(
        "Accounting transaction keys", f"{_FISCAL_YEAR_PREFIX}/accounting-transaction-keys"
    ),
    EndpointSpec("Asset stocktakings", f"{_FISCAL_YEAR_PREFIX}/assets/stocktakings"),
    EndpointSpec(
        "Posting proposal rules (incoming invoices)",
        f"{_FISCAL_YEAR_PREFIX}/posting-proposal-rules-incoming-invoices",
    ),
    EndpointSpec(
        "Posting proposal rules (outgoing invoices)",
        f"{_FISCAL_YEAR_PREFIX}/posting-proposal-rules-outgoing-invoices",
    ),
    EndpointSpec("Terms of payment", f"{_FISCAL_YEAR_PREFIX}/terms-of-payment"),
]

# --- Global/unscoped endpoints (decision #3) ---
#
# accounting-clients and master-data clients are content-negotiated (JSON
# or XML) same as the scoped endpoints above; addressees/banks/employees
# and both DMS routes are JSON-only in the live app (bare list return, no
# Accept-header branching) -- `_export_one` detects this from the actual
# response content-type rather than assuming it here.
GLOBAL_ENDPOINTS = [
    EndpointSpec("Accounting clients", "/datev/api/accounting/v1/clients"),
    EndpointSpec("Master-data clients", "/datev/api/master-data/v1/clients"),
    EndpointSpec("Master-data addressees", "/datev/api/master-data/v1/addressees"),
    EndpointSpec("Master-data banks", "/datev/api/master-data/v1/banks"),
    EndpointSpec("Master-data employees", "/datev/api/master-data/v1/employees"),
    EndpointSpec("DMS domains", "/datev/api/dms/v1/domains"),
    EndpointSpec("DMS documents", "/datev/api/dms/v1/documents"),
]


def _scope_for(path_template: str, client_id: str, fiscal_year_id: str) -> dict[str, str]:
    placeholders = set(_PLACEHOLDER_RE.findall(path_template))
    scope: dict[str, str] = {}
    if "client_id" in placeholders:
        scope["client_id"] = client_id
    if "fiscal_year_id" in placeholders:
        scope["fiscal_year_id"] = fiscal_year_id
    if "cost_system_id" in placeholders:
        scope["cost_system_id"] = DEMO_COST_SYSTEM
    return scope


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _export_one(
    client: TestClient,
    resource_name: str,
    url_path: str,
    scope: dict[str, str],
    manifest: list[dict[str, Any]],
) -> None:
    rel = url_path.lstrip("/")  # e.g. "datev/api/accounting/v1/clients/.../creditors"

    json_resp = client.get(url_path, headers={"Accept": "application/json"})
    default_resp = client.get(url_path)
    json_resp.raise_for_status()
    default_resp.raise_for_status()

    json_path_rel = f"{rel}.json"
    _write(_DATA_DIR / f"{rel}.json", json_resp.content)

    xml_path_rel: Optional[str] = None
    if "xml" in default_resp.headers.get("content-type", ""):
        xml_path_rel = f"{rel}.xml"
        _write(_DATA_DIR / f"{rel}.xml", default_resp.content)

    manifest.append(
        {
            "endpoint": url_path,
            "scope": scope if scope else "global",
            "resource_name": resource_name,
            "json_path": json_path_rel,
            "xml_path": xml_path_rel,
        }
    )


def main() -> None:
    if _DATA_DIR.exists():
        shutil.rmtree(_DATA_DIR)
    _DATA_DIR.mkdir(parents=True)

    manifest: list[dict[str, Any]] = []
    client = TestClient(app)

    for spec in SCOPED_ENDPOINTS:
        seen_paths: set[str] = set()
        for client_id in DEMO_CLIENTS:
            for fiscal_year_id in DEMO_FISCAL_YEARS:
                url_path = spec.path_template.format(
                    client_id=client_id,
                    fiscal_year_id=fiscal_year_id,
                    cost_system_id=DEMO_COST_SYSTEM,
                )
                if url_path in seen_paths:
                    # Same URL for multiple demo combos (e.g. "fiscal
                    # years" only varies by client_id) -- already exported.
                    continue
                seen_paths.add(url_path)
                scope = _scope_for(spec.path_template, client_id, fiscal_year_id)
                _export_one(client, spec.resource_name, url_path, scope, manifest)

    for spec in GLOBAL_ENDPOINTS:
        _export_one(client, spec.resource_name, spec.path_template, {}, manifest)

    manifest.sort(key=lambda entry: (entry["resource_name"], entry["endpoint"]))
    (_DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    file_count = sum(1 for path in _DATA_DIR.rglob("*") if path.is_file())
    print(f"Generated {len(manifest)} resources, {file_count} files, under {_DATA_DIR}")


if __name__ == "__main__":
    main()
