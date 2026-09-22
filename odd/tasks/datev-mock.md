# DATEV Local API Mock — Tasks

Engram mirror: pending (Engram MCP not connected this session).

## Objective
FastAPI mock of DATEV's local Desktop API (master-data/v1/clients, accounting/v1/clients, diagnostics/v1/echo), serving exact DataContractSerializer-style XML on port 58452, with Swagger UI for manual testing. See approved plan: `C:\Users\eloadmin\.claude\plans\the-idea-is-to-cheerful-hopcroft.md`.

## Epic
**DATEV Desktop API Mock** — one epic covering the full RED → GREEN → REFACTOR cycle for the 3-endpoint FastAPI mock.

## Scope / constraints
- No real values from `examples/*.xml` reused — shape only.
- XML responses must match real namespaces/root elements/`i:nil` convention exactly.
- Same port (58452) as real API; switching mock↔real is a base-URL config change only, no hosts/DNS edits.
- **TDD: Strict TDD Mode is enabled for this session** (source: global `CLAUDE.md` instruction). This supersedes the earlier note in this file about "ordinary functional verification" — the workflow is **RED (failing tests) → GREEN (implementation) → REFACTOR**, not manual curl/Swagger checks alone. The plan's original "Verification" section (manual curl/Swagger walkthrough) is retained as a post-GREEN sanity check, not as the primary correctness signal.

## Decisions

### Accounting `/clients` format discrepancy — XML vs JSON (2026-09-22)
Discovered a real conflict between two sources for the same logical endpoint:

- **Real-traffic capture** (`examples/JUS_clients.xml`): the accounting
  `/clients` endpoint returns **XML** (.NET `DataContractSerializer` format,
  `ArrayOfClient` root) on **port 58452** over **HTTPS**. This is what the
  existing plan and `tests/test_accounting.py` were built against.
- **Official current DATEV developer docs** (developer.datev.de, Accounting
  product v1.7.4, Desktop API): the exact same logical endpoint
  (`GET /datev/api/accounting/v1/clients`) is documented as returning
  **JSON** on **port 58454** over **plain HTTP**, with this confirmed example
  response body:

  ```json
  [
    {
      "company_data": {
        "creditor_identifier": "DE98ZZZ09999999999"
      },
      "id": "78a11a29-2a32-4a5e-a73b-632f6aeae131",
      "name": "DATEVconnect GmbH",
      "number": "47011"
    }
  ]
  ```

**User's decision: support both formats** via HTTP content negotiation on
the *same* endpoint and port (58452, matching the real environment) — do
**not** add a second port binding for 58454; that was explicitly ruled out
as unnecessary complexity.

- `Accept: application/json` → JSON array matching the documented shape
  above: `id` (string GUID), `name` (non-empty string), `number` (**string**
  — the docs example shows `"number":"47011"` as a string, not an integer,
  unlike the XML `Number` which is int-like text; this discrepancy is
  preserved faithfully, not silently coerced), and `company_data` (object,
  may be `null`/absent for records without it, mirroring `CompanyData`'s
  `i:nil="true"` in the XML shape — but at least one fake-dataset record has
  a populated `company_data.creditor_identifier` so both branches are
  exercised in tests).
- `Accept: application/xml` (or no explicit preference / current default
  behavior) → the existing planned XML shape, unchanged (`ArrayOfClient`
  root, `Client` elements with `Id`, `Parent`, `membersToSerialize`,
  `AccountingProductivities`, `ClientGuid`, `CompanyData`, `Name`, `Number`).

**Explicit scope boundary** (do not expand beyond this):
- Master Data (`master-data/v1/clients`) and Diagnostics (`diagnostics/v1/echo`)
  stay **XML-only**, unchanged from the existing plan/tests — there is no
  confirmed official JSON spec for those two endpoints, so none is invented.
- The documented OData-style query params (`select`, `filter`, `skip`, `top`,
  `expand`) are **out of scope** — explicitly noted as a later stretch, not
  built or tested now.

New tests covering the JSON branch: `tests/test_accounting_json.py`.

## Tasks

### Epic: DATEV Desktop API Mock

- [x] **T0 — Write RED-phase test suite** (this step)
  `tests/conftest.py`, `tests/test_diagnostics.py`, `tests/test_master_data.py`, `tests/test_accounting.py`, plus root `requirements.txt`. Tests are written against `app.main.app`, which does not exist yet — collection is expected to fail with `ModuleNotFoundError` (RED). No `app/` or `certs/` code was written in this task.
  Run with: `python -m pytest tests/ -v` (from `C:\Users\eloadmin\DATEV-Mock`; expected result right now: collection error on `from app.main import app`, which is correct RED).

- [x] **T1 — Scaffold project**
  `requirements.txt` (done in T0), `app/` package init, `certs/generate_cert.py` (self-signed cert generation via `cryptography`).

- [x] **T2 — `app/models.py`**
  Dataclasses for `ClientResource` (42-field layout, see note below), `Client` (accounting, 8 XML fields + JSON-only `company_data`), `Echo`.

- [x] **T3 — `app/fake_data.py`**
  Seeded synthetic dataset generation (`random.seed(42)`), no real values. Satisfies T0's cardinality assertions: 18 `ClientResource` records (≥15), 5 accounting `Client` records (≥3), unique `Number` values, at least one record with `Note`/`RiskAssessment` left `i:nil="true"`.
  Per "## Decisions": the first accounting `Client` record carries a populated `company_data.creditor_identifier`; the rest leave `company_data` unset (`None` → JSON `null`). No change to the XML shape.

- [x] **T4 — `app/xml_serializers.py`** + **`app/json_serializers.py`**
  Hand-built XML rendering via string templates (not `ElementTree` — its serializer cannot reproduce the real contract's per-field bare `xmlns=` namespace overrides without hoisting to `ns0`/`ns1` prefixes) for all 3 XML shapes. Satisfies T0's structural assertions (root tags, namespaces, field presence/order, `i:nil` attribute behavior).
  Added separate `app/json_serializers.py` for the accounting JSON branch (`id`, `name`, `number`-as-string, optional `company_data.creditor_identifier`), keeping XML and JSON building in clearly separate modules. Master Data and Diagnostics stay XML-only.

- [x] **T5 — `app/routers/{diagnostics,master_data,accounting}.py` + `app/main.py`**
  FastAPI app wiring, `Content-Type: application/xml` responses, Swagger-visible docs. Echo endpoint generates a fresh `id` (uuid4) and timestamp per call.
  Accounting router does content negotiation on the same port (58452): `Accept: application/json` → JSON branch, `Content-Type: application/json`; `application/xml` or no explicit preference → existing XML behavior. Master Data and Diagnostics routers unaffected. OData-style query params remain out of scope, not implemented.

- [x] **T6 — `README.md`** *(already done, written earlier)*
  Run instructions, cert generation, mock-vs-real switch explanation.

- [x] **T7 — GREEN verification + manual sanity check**
  `python -m pytest tests/ -v` → **32 passed** (all green, no test file modified). `certs/generate_cert.py` sanity-run confirmed: produces `certs/cert.pem` / `certs/key.pem` without error (both gitignored via existing `certs/*.pem` rule). Manual curl/Swagger walkthrough against a live `uvicorn` server was out of scope for this pass (TestClient covers behavior; not started per instructions).

## Note on field count discrepancy (found while writing T0)
The task brief describing `ClientResource` said "exactly these 41 child elements" but the enumerated list that followed has **42** entries (verified by literal count). `tests/test_master_data.py` treats the enumerated field list as authoritative (not the "41" label) and asserts presence of all 42 named fields via `EXPECTED_FIELDS`, derived from the list rather than a hardcoded count. Flagged here for T2/T4 implementers and for the user to confirm against the real `examples/clients.xml` shape during GREEN.

## Route
- **T0 (this step): direct inline / delegated-direct write** — 4 test files + 1 requirements file + this task doc, mechanical once the field/namespace spec was fixed from the plan. No unresolved design decisions.
- **T1–T6: delegated direct** — one writer for 6+ non-trivial files, per Writer trigger. Blocked until the user approves this RED-phase test suite.
- **T7: orchestrator-run verification** — pytest run + manual curl/Swagger checks, after T1–T6 land.

## Progress
- Plan approved 2026-09-22.
- Task file created 2026-09-22, before first source write.
- 2026-09-22: T0 complete — RED-phase test suite written (`tests/conftest.py`, `tests/test_diagnostics.py`, `tests/test_master_data.py`, `tests/test_accounting.py`) plus `requirements.txt`. No `app/` or `certs/` code exists yet; suite fails on collection (`ModuleNotFoundError: No module named 'app'`), which is the correct RED state. Next step: user approval, then T1–T6 (GREEN implementation).
- 2026-09-22: Real-vs-docs conflict found and resolved with the user — see "## Decisions" above. Decision: accounting `/clients` supports both XML (existing) and JSON (new, per official docs) via content negotiation on port 58452, no second port. Added `tests/test_accounting_json.py` (still RED — fails on collection like the rest of the suite, no `app/` code written). Updated T3/T4/T5 task descriptions accordingly. Master Data, Diagnostics, and OData query params remain explicitly out of scope.
- 2026-09-22: GREEN phase complete. Implemented `app/` (models, fake_data, xml_serializers, json_serializers, routers/{diagnostics,master_data,accounting}, main) and `certs/generate_cert.py`, without editing any test file. `python -m pytest tests/ -v` → `32 passed, 2 warnings in 0.42s` (first clean run, no fixes needed after initial implementation). Cert generator sanity-run confirmed working. T1–T5 and T7 checked off; T6 (README) was already done earlier. Next step: optional REFACTOR pass / user review, then git commit (not done by this task — handled separately per instructions).
