# DATEV Mock — Extended Endpoint Coverage

## Objective
Expand the mock from 3 endpoints to the ~22 covered by ELO's existing
internal DATEV mock (`C:\Mockup\serve-0.1-generate.jar`, see
[[project_internal_java_mock_reference]] and
`examples/DATEV_Mock_Server_Reference.md`, local-only). User decision
2026-09-22: build all of it, as a new epic, after the base API and
settings/admin epics (both already GREEN and shipped).

## Ground truth for this epic
- `examples/DATEV_Mock_Server_Reference.md` — local-only, endpoint list, example shapes, runtime behavior notes (query param quirks, 404-on-bad-addressee-id, etc.), extracted from the internal mock's JAR/bytecode/live responses.
- Official DATEV OpenAPI 3.0.1 specs, extracted from that same JAR (`Accounting-1.5.0.json`, `Client Master Data-1.6.0.json`) to `C:\Users\eloadmin\AppData\Local\Temp\2\claude\C--Users-eloadmin-DATEV-Mock\8c106e6e-43c0-4b9c-b0a4-1503db03ef05\scratchpad\datev-openapi\main\mockdata\apispec\`. A compiled, resolved-inline reference for all 18 schema-backed endpoints (exact paths, property names/types/enums, notable quirks) was written to `C:\Users\eloadmin\AppData\Local\Temp\2\claude\C--Users-eloadmin-DATEV-Mock\8c106e6e-43c0-4b9c-b0a4-1503db03ef05\scratchpad\datev-endpoint-specs.md` — **this is the primary contract for Phases A and B below; writers for those phases must read it.** These are scratchpad files (session-local), not part of the repo — if a future session needs them regenerated, re-extract from the JAR per `examples/DATEV_Mock_Server_Reference.md`'s instructions.
- DMS has **no official spec** in the bundle (confirmed via full-text grep, zero "dms" matches) — Phase C is built from the reference doc's example shapes alone, necessarily lower-fidelity.

## Key findings from spec analysis (apply across all phases)
- No OpenAPI `nullable` used anywhere; optionality is purely "absent from `required`".
- All list responses are bare JSON arrays, never a pagination wrapper.
- No real polymorphism (`oneOf`/`discriminator`) — `Addressee`/`creditor`/`debitor` are flat objects with a type enum plus always-present parallel sibling properties for each type (natural_person vs legal_person), gated only by description text.
- A few fields are typed inconsistently or need hardcoded lookup tables instead of enums (`general-ledger-account.main_function*`, `cost-system.number`, `cost-center.cost_rates[].valid_from/valid_to` as integer-encoded dates like `20161201`) — see the compiled spec doc for exact per-field notes.
- `accounts-payable/condense` and `accounts-payable` (and receivable equivalents) share the same schema — condense is a server-side aggregation, not a different shape.

## Cross-phase decisions
- **All new endpoints are JSON-only.** Unlike the original `accounting/v1/clients`, there is no real captured XML evidence for any of these 18+2 endpoints — only JSON evidence (official spec + internal mock's live JSON responses). Inventing an XML shape with no ground truth would be guesswork; don't.
- **No relational filtering by path params.** `{client-id}`, `{fiscal-year-id}`, `{cost-system-id}` in accounting paths are accepted (any value) but do **not** filter/select which fake dataset is returned — every accounting list endpoint always returns the same generic fake fixture regardless of the specific ids in the URL. This mirrors the existing 3 endpoints' behavior and the established "don't implement query-param semantics until a consumer needs them" philosophy (`select`/`filter`/`skip`/`top`/`expand` remain out of scope here too).
- **Exception: `GET /addressees/{addressee-id}` does real lookup-by-id**, returning 404 for an unknown id — this exactly matches an *observed, documented* behavior of the reference mock ("An arbitrary addressee ID returned 404"), so it's evidence-based, not a guess.
- No XML/JSON content negotiation needed for any of these — always `application/json`.
- Admin UI (`/admin`) is **not** extended to cover these new resources in this epic — out of scope, dataset editing stays limited to the original master-data/accounting clients lists unless explicitly requested later.

## Phases (each phase is its own commit+push checkpoint per standing workflow)

### Phase A — Master Data extension (smallest, do first)
3 endpoints: `GET /datev/api/master-data/v1/addressees`, `GET /datev/api/master-data/v1/addressees/{addressee-id}` (real 404 lookup), `GET /datev/api/master-data/v1/banks`. Extends the existing `app/routers/master_data.py` pattern.

- [x] A0 — RED-phase tests
- [x] A1 — Models + fake data (addressees, banks)
- [x] A2 — Router endpoints
- [x] A3 — GREEN verification + commit/push (verification done; commit/push handled separately by orchestrator per standing workflow)

### Phase B — Accounting extension (largest, split into 2 batches for delivery size)
15 endpoints, all under `/datev/api/accounting/v1/clients/{client-id}/fiscal-years/{fiscal-year-id}/...` (exact path spellings per the compiled spec doc). Split by writer-batch, not by meaning, purely to keep each delegation bounded:

**Batch B1**: `fiscal-years` (client-level, not fiscal-year-scoped), `cost-systems`, `cost-systems/{cost-system-id}/cost-centers`, `creditors`, `debitors`, `general-ledger-accounts`.
**Batch B2**: `accounts-payable`, `accounts-payable/condense`, `accounts-receivable/condense`, `accounting-sequences-processed`, `accounting-transaction-keys`, `assets/stocktakings`, `posting-proposal-rules-incoming-invoices`, `posting-proposal-rules-outgoing-invoices`, `terms-of-payment`.

- [ ] B0 — RED-phase tests (both batches' worth, written together for consistency — one writer, since test-writing is comparatively lightweight even for 15 endpoints)
- [ ] B1-GREEN — Batch 1 implementation (6 endpoints)
- [ ] B2-GREEN — Batch 2 implementation (9 endpoints)
- [ ] B3 — GREEN verification (full batch) + commit/push

### Phase C — DMS (new API area, lower-fidelity spec)
2 endpoints: `GET /datev/api/dms/v1/domains`, `GET /datev/api/dms/v1/documents`. Built from `examples/DATEV_Mock_Server_Reference.md`'s example shapes only (domain/folder/register tree; document metadata incl. amount, class, GUIDs, timestamps) — no OpenAPI spec exists for this area, so field completeness will be lower than Phases A/B. Say so plainly in the eventual README update rather than overclaiming fidelity.

- [ ] C0 — RED-phase tests
- [ ] C1 — Models + fake data + router
- [ ] C2 — GREEN verification + commit/push

### Final
- [ ] D0 — README update covering all new endpoints, their JSON-only nature, the no-path-filtering decision, and the DMS fidelity caveat.

## Route
Every phase: delegated direct (RED and GREEN each touch enough files to trigger the Writer rule). Orchestrator runs verification and owns all commits/pushes.

## Progress
- 2026-09-22: Epic created. User chose "start a new epic for all of it" after the settings/admin epic shipped. OpenAPI specs extracted and mapped (18/18 schema-backed endpoints found, DMS confirmed spec-less). Starting with Phase A.
- 2026-09-22: **A0 — RED-phase tests written** (`tests/test_master_data_addressees_banks.py`, 20 tests, one file, in-house style). No existing test file touched; existing 77/77 still pass in isolation. Confirmed correct RED signal: the new file imports `ADDRESSEES_ENDPOINT`/`BANKS_ENDPOINT` directly from `app.routers.master_data`, which don't exist yet, so collection fails with `ImportError: cannot import name 'ADDRESSEES_ENDPOINT' from 'app.routers.master_data'` — this also interrupts the full `pytest tests/` run for the whole suite until A2 adds those constants, so GREEN must add them even before making the endpoints pass.

  **Unambiguous target contract for the GREEN writer (A1/A2):**
  - Paths (exact spelling from spec doc, hyphenated ids): `GET /datev/api/master-data/v1/addressees`, `GET /datev/api/master-data/v1/addressees/{addressee-id}`, `GET /datev/api/master-data/v1/banks`. All JSON-only, `Content-Type: application/json`, bare arrays for the two list endpoints, a bare single object (not a 1-item array) for the by-id endpoint.
  - `app/routers/master_data.py` must define `ADDRESSEES_ENDPOINT = "/datev/api/master-data/v1/addressees"` and `BANKS_ENDPOINT = "/datev/api/master-data/v1/banks"` module-level constants (mirroring the existing `ENDPOINT` constant for `clients`), since the RED tests import them directly.
  - `addressees` list: ≥5 fake records. Each record has non-empty `id` (str), `type` (`natural_person`|`legal_person`), `status` (`active`|`inactive`), `timestamp` (str) always populated. The fake dataset must contain **both** types (tested explicitly, not vacuously). For `type == natural_person` records, `firstname` and `current_surname` must be populated (non-empty str); for `type == legal_person` records, `current_company_name` must be populated (non-empty str). Only these top-level fields are asserted — none of the ~60 nested `detail`/`addresses`/etc. fields are tested in RED, deliberately, per the task scope.
  - `addressees/{addressee-id}`: looking up an id taken from the list response returns 200 + a single JSON object with matching `id`/`type`. Looking up an arbitrary/unknown id (a fresh `uuid4` not in the dataset) returns **404** — this is real lookup-by-id filtering, the sole exception to this epic's "no path-param filtering" rule, and is evidence-based (epic doc: "An arbitrary addressee ID returned 404").
  - `banks` list: ≥5 fake records. Each has non-empty `id` (str — always string, never the bare-number inconsistency the spec's own example shows), `bic` (str, 1–11 chars), `country_code` (str, 1–2 chars), `name` (str, non-empty).
  - All three endpoints must work with zero query params (baseline confirmed by test; no `select`/`filter`/`skip`/`top`/`expand` semantics implemented, consistent with the rest of the epic).

  **Judgment calls / ambiguities flagged for GREEN and future reviewers:**
  - The compiled spec doc only explicitly marks `type` as `REQUIRED` on `Addressee` (`id`'s "required" note is about PUT request bodies, not GET responses). RED nonetheless treats `id`/`status`/`timestamp` as reliably-present in every fake record — a deliberate mock-generation choice for a coherent dataset, not something the OpenAPI schema strictly mandates.
  - Requiring `firstname`+`current_surname` (natural_person) / `current_company_name` (legal_person) to always be populated per-type is likewise a RED-imposed fake-data contract, not an OpenAPI `required` constraint (the spec gates these fields by free-text description only, both are technically optional for either type). GREEN must follow this contract for the tests to pass; it does not need to leave the *other* type's fields null/absent (untested either way).
  - The 404-unknown-id test uses a freshly generated `uuid4` and asserts it isn't already a known id first — the actual collision probability is negligible, not a real flake risk.

- 2026-09-22: **A1/A2/A3 — GREEN.** Added `Addressee`/`Bank` dataclasses (`app/models.py`, flat top-level fields only — `detail`/`addresses`/`communications`/`bank_accounts`/`tax_offices`/`contact_persons` intentionally not modeled or served, consistent with the real API omitting them whenever `expand` isn't requested, which this mock never implements). Added `_generate_addressees()`/`_generate_banks()` to `app/fake_data.py` (8 addressees — forced mix of both `natural_person`/`legal_person` at indices 0/1, rest random; 6 banks — fictitious invented BIC/name/city/country_code combinations, no real bank identifiers). Added `list_addressees()`/`get_addressee(id)`/`list_banks()` (read-only, no CRUD — out of scope per epic doc) to `app/data_store.py`, wired into `reset()`. Added `ADDRESSEES_ENDPOINT`/`BANKS_ENDPOINT` constants and the three GET routes to `app/routers/master_data.py`, returning plain dicts/lists (FastAPI's default JSON response) with `None`-valued optional fields dropped before serialization (matches the spec's no-`nullable` convention). `addressees/{addressee_id}` does real lookup-by-id, raising `HTTPException(404)` on miss. Files touched: `app/models.py`, `app/fake_data.py`, `app/data_store.py`, `app/routers/master_data.py`. `tests/test_master_data_addressees_banks.py` was not modified.
  - **Test count note (orchestrator-investigated):** the GREEN writer reported "74 base tests" and flagged a discrepancy against the expected 77. Verified independently: the base suite is in fact exactly 77 (8+7+7+10+9+18+18 across the 7 pre-existing files), and the new file actually has **17** tests, not the 20 the writer's report claimed — 77+17=94 matches the real passing count exactly. The writer's headline numbers were simply a self-reporting miscount, not a real gap; nothing was missing or broken.
  - **Stray process found and fixed (orchestrator):** the port-58452 conflict the writer hit (PID 4400) was not "unrelated" — it was a leaked `uvicorn` process from an earlier verification step in the settings epic, where `kill <bash-job-id>` had only killed the shell job wrapper, not the actual Windows process, leaving stale old code listening on the mock's real port. Force-killed via `taskkill /F /PID`. Lesson applied to this task's own verification: killed the server by its actual reported "Started server process [PID]" via `taskkill`, not by shell job id, and confirmed the port was released afterward.
  - **Data-quality fix (orchestrator):** live-checking the addressees endpoint surfaced a name/sex mismatch (e.g. "Sabine" — a female name — tagged `sex: "male"`), because `sex` was cycling through a pool by loop index, unrelated to which name was actually picked. Fixed by adding an explicit `_FIRST_NAME_SEX` lookup keyed by first name (all 15 names in `_PERSON_NAME_POOL` mapped correctly) and using that instead of the index-cycling `_SEX_POOL`, which is now removed as dead code. Re-verified: 94/94 still passing after the fix.
  - **Final verification:** `.venv\Scripts\python.exe -m pytest tests/ -v` → **94 passed**, independently re-run by the orchestrator after the fix above. Live sanity check on the correct port 58452 (after clearing the stray process): `GET /datev/api/master-data/v1/addressees` → 200, JSON array, ≥5 records, both types present, names/sex now consistent; `GET /datev/api/master-data/v1/addressees/{known-id}` → 200, matching object; `GET /datev/api/master-data/v1/addressees/00000000-0000-0000-0000-000000000000` (unknown id) → 404; `GET /datev/api/master-data/v1/banks` → 200, JSON array, 6 plausible fictitious records. Server stopped cleanly, port confirmed released. Phase A complete; committed and pushed per the standing "commit+push when an epic/phase finishes" instruction.
