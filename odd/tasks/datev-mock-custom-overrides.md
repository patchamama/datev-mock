# DATEV Mock — Custom Example Overrides (Upload XML/JSON)

## Objective
User request (2026-09-23, Spanish): let the admin frontend accept an
uploaded XML or JSON file as a **temporary, in-memory override** for a
specific mocked endpoint's response. The system must **automatically
detect** which endpoint an uploaded file corresponds to from its
structure, tell the user which endpoint it matched, and let them toggle
per-endpoint between "serve the uploaded file" and "serve the app's normal
generated data."

## Design

### Storage (in-memory only, never persisted to disk)
`app/overrides.py` — a module-level dict keyed by **endpoint key** (see
table below), each entry: `{content: str, content_type: "xml"|"json",
filename: str, uploaded_at: iso str, enabled: bool}`. Lost on restart, by
design — consistent with how dataset edits already work
([[datev-mock-settings]]). No new dependency on `app/config.py`'s
`settings.json` persistence.

### Detection
Two passes, cheapest first:
1. **Try XML** (`xml.etree.ElementTree.fromstring`): on success, take the
   root tag's local name (strip `{namespace}` prefix) and look it up in a
   fixed map. Exactly 3 possible XML root tags in this whole mock:
   `Echo` → `diagnostics.echo`, `ArrayOfClientResource` →
   `master_data.clients`, `ArrayOfClient` → `accounting.clients`.
2. **Try JSON** (`json.loads`): on success, take the field-name set of the
   first array element (or of the top-level object, if not an array), and
   match against the fingerprint table below. A fingerprint is a small set
   of field names that must ALL be present — chosen to be as distinctive
   as possible, but several DATEV resources are **structurally identical**
   to each other (same OpenAPI schema, confirmed during the
   extended-endpoints epic), so detection can legitimately return **more
   than one candidate**. That's correct behavior, not a bug — handle it
   honestly (ask the user to pick), never guess.

Detection returns a `list[str]` of candidate endpoint keys: empty (no
match — reject with a clear error), one (auto-assign), or multiple
(ambiguous — frontend must ask the user to choose one of the listed
candidates before the override becomes active).

### Endpoint key table (all 23 mocked GET endpoints; keys are the contract other code reads/writes)

| Key | Real path | Format | Detection |
|---|---|---|---|
| `diagnostics.echo` | `/datev/api/diagnostics/v1/echo` | XML | root tag `Echo` |
| `master_data.clients` | `/datev/api/master-data/v1/clients` | XML | root tag `ArrayOfClientResource` |
| `accounting.clients` | `/datev/api/accounting/v1/clients` | XML or JSON | root tag `ArrayOfClient` (XML) OR fields `{id,name,number}` (JSON) |
| `master_data.addressees` | `.../master-data/v1/addressees` | JSON | fields `{type,status,timestamp}` + (`firstname` or `current_company_name`) |
| `master_data.banks` | `.../master-data/v1/banks` | JSON | fields `{bic,country_code}` |
| `accounting.fiscal_years` | `.../fiscal-years` | JSON | fields `{account_system,currency_code,legal_form,taxation_method}` |
| `accounting.cost_systems` | `.../cost-systems` | JSON | fields `{short_name,is_activated_for_postings}` |
| `accounting.cost_centers` | `.../cost-centers` | JSON | fields `{long_name,short_name,creation_date}` |
| `accounting.creditors` **or** `accounting.debitors` (ambiguous pair — identical schema) | `.../creditors`, `.../debitors` | JSON | fields `{addressee_id,business_partner_number,legal_entity_type}` |
| `accounting.general_ledger_accounts` | `.../general-ledger-accounts` | JSON | fields `{account_number,caption,main_function,main_function_number}` |
| `accounting.accounts_payable` **or** `accounting.accounts_payable_condense` **or** `accounting.accounts_receivable_condense` (ambiguous triple — identical schema) | `.../accounts-payable[/condense]`, `.../accounts-receivable/condense` | JSON | fields `{amount_debit,amount_credit,evidence_type,debit_credit_identifier}` |
| `accounting.accounting_sequences_processed` | `.../accounting-sequences-processed` | JSON | fields `{accounting_sequence_id,record_type,accounting_reason,date_from,date_to}` |
| `accounting.accounting_transaction_keys` | `.../accounting-transaction-keys` | JSON | fields `{tax_rate,is_tax_rate_selectable}` |
| `accounting.assets_stocktakings` | `.../assets/stocktakings` | JSON | fields `{asset_number,inventory_number}` |
| `accounting.posting_proposal_rules_incoming` **or** `accounting.posting_proposal_rules_outgoing` (ambiguous pair — identical schema) | `.../posting-proposal-rules-{incoming,outgoing}-invoices` | JSON | fields `{assignment_criteria,posting_proposal_information,uncertain_label}` |
| `accounting.terms_of_payment` | `.../terms-of-payment` | JSON | fields `{caption,due_type}` |
| `dms.domains` | `/datev/api/dms/v1/domains` | JSON | fields `{name,type}` where `type` ∈ `{domain,folder,register}`, no `amount`/`document_class` |
| `dms.documents` | `/datev/api/dms/v1/documents` | JSON | fields `{amount,document_class,domain_id,created_at,modified_at}` |

Not overridable (excluded, deliberately): `master_data.addressees/{id}` —
a lookup derived from the addressees list, not its own independent
resource; overriding the list already covers the meaningful case.

### Admin API (`app/routers/admin.py`, new endpoints)
- `POST /admin/api/overrides` — multipart file upload (needs the
  `python-multipart` package — **add it to `requirements.txt`**, it's not
  there yet). Detects candidates. Exactly one candidate → stores content,
  **enables it immediately**, responds `{"status": "matched", "endpoint":
  "<key>"}`. Multiple candidates → stores content in a pending/unassigned
  slot (not yet tied to any endpoint, not yet enabled), responds
  `{"status": "ambiguous", "candidates": ["<key>", ...], "pending_id":
  "<uuid>"}`. Zero candidates → `422` `{"status": "unrecognized"}`, nothing
  stored.
- `POST /admin/api/overrides/resolve` — body `{"pending_id": "...",
  "endpoint": "<key>"}` (key must be one of the candidates that upload
  call returned) — assigns the pending content to that endpoint and
  enables it.
- `GET /admin/api/overrides` — list all endpoints that currently have an
  override stored (key, filename, content_type, enabled, uploaded_at).
- `PUT /admin/api/overrides/{key}` — body `{"enabled": bool}` — toggle
  between serving the override and the app's normal generated data,
  without deleting the stored file (so a user can flip back and forth).
- `DELETE /admin/api/overrides/{key}` — removes the override entirely;
  that endpoint reverts to normal generated data.

### Router integration (the part that actually serves overrides)
Every GET handler across `diagnostics.py`, `master_data.py`,
`accounting.py`, `dms.py` must, near the top, check
`overrides.get_active_override(<its own key>)`; if present, return a
`Response(content=override.content, media_type=<"application/xml" or
"application/json" matching override.content_type>)` **instead of** its
normal generated response — bypassing serialization, fake data, and (for
`accounting.clients`) the usual XML/JSON content-negotiation entirely
(an active override always wins, regardless of the request's `Accept`
header — it's an explicit override, negotiation doesn't apply once one is
active). If no active override, behave exactly as today.

## Scope boundaries
- In-memory only — no disk persistence, no survival across restart.
- No validation that an uploaded file is "correct" beyond structural
  endpoint-detection — a user can upload garbage-but-detectable content
  and it will be served as-is; that's the point (custom test scenarios).
- The 3 ambiguous groups require a manual pick in the UI — do not attempt
  a fragile heuristic to auto-disambiguate them (e.g. presence of
  `dunning_level` hinting at receivables) — real user-authored files won't
  reliably carry that signal either. Be honest about the ambiguity.
- `master_data.addressees/{id}` is not an override target (see above).

## Tasks
- [x] V0 — RED-phase tests: `app/overrides.py`'s detection/storage
      contract (all 22 override-eligible keys' fingerprints, the 3 ambiguous
      groups resolving to multiple candidates, 0-candidate rejection) +
      `/admin/api/overrides*` HTTP contract (upload/resolve/list/toggle/
      delete, single-match vs ambiguous vs unrecognized responses).
- [x] V1-GREEN — `app/overrides.py` (detection + in-memory store) +
      `requirements.txt` (`python-multipart`).
- [x] V2-GREEN — `/admin/api/overrides*` endpoints in `admin.py`.
- [x] V3 — RED+GREEN for router integration: a small, focused test per
      router file confirming an enabled override is served verbatim and
      a disabled/absent one falls through to normal behavior, then wire
      the actual override-check into all 4 router files' handlers.
- [x] V4 — Frontend: an "Custom Examples" card in `/admin` — file picker +
      upload button, ambiguous-match resolution UI (radio/select among
      candidates + confirm), a table of current overrides with an
      enable/disable toggle and delete button per row, and a clear
      "matched to: `<endpoint>`" confirmation message after a successful
      single-match upload. Proportional smoke-test coverage, same
      rationale as [[datev-mock-admin-ui-polish]]'s U1.
- [x] V5 — README update (new admin feature section) + commit/push.

## Route
V0: delegated direct (one writer, comprehensive test suite). V1/V2:
delegated direct (one writer, builds the module + admin API against V0's
tests). V3: delegated direct (one writer, RED+GREEN together since it's a
small, mechanical, well-specified integration step repeated across 4
files). V4: delegated direct (one writer, frontend). V5: orchestrator.
Orchestrator verifies and commits after each major step, same discipline
as every prior epic in this project.

## Progress
- 2026-09-23: Epic created, full design/fingerprint table settled before any delegation.
- 2026-09-23: V0 RED-phase tests written — `tests/test_overrides.py` (24
  tests) + `tests/test_overrides_api.py` (6 tests). Both fail correctly at
  collection today (`ImportError: cannot import name 'overrides' from
  'app'`, confirmed by running pytest). Existing 170 tests untouched and
  still passing (`--ignore` the two new files). No fingerprint-field
  discrepancies found against `app/models.py` — every field name in the
  task doc's table (including the "extra confidence" quirk fields
  `main_function`/`main_function_number`/`dunning_level` mentioned in the
  task instructions) matches the dataclasses exactly, and all JSON router
  handlers (`accounting.py`, `master_data.py`, `dms.py`,
  `json_serializers.py`) emit those field names verbatim (snake_case
  `asdict`, no renaming) — confirmed `accounting.clients`' JSON form keys
  are `id`/`name`/`number` (lowercase) via `json_serializers.py`. One
  clarification (not a discrepancy): the table's own key count is 22
  override-eligible keys, not 23 — the 23rd mocked GET endpoint,
  `master_data.addressees/{id}`, is the doc's own explicitly-excluded
  non-target, so it was never counted as a detection candidate.

  **Settled `app/overrides.py` contract for V1-GREEN:**
  - `detect_candidates(content: str) -> list[str]`
  - `set_override(key: str, content: str, content_type: str, filename: str) -> None`
    (enabled=True by default)
  - `get_active_override(key: str) -> Override | None` (an `Override`
    dataclass/object with `.content`, `.content_type`, `.filename`,
    `.uploaded_at`, `.enabled`; returns `None` unless `enabled` is `True`)
  - `list_overrides() -> dict[str, dict]` (key -> metadata incl. `enabled`;
    includes disabled entries)
  - `set_enabled(key: str, enabled: bool) -> None`
  - `delete_override(key: str) -> None`
  - `clear_all_overrides() -> None` (test-only helper, also used by
    `tests/test_overrides_api.py`'s local isolation fixture)
  - `store_pending(content: str, content_type: str, filename: str, candidates: list[str]) -> str`
    (returns a `pending_id` uuid string) — not directly unit-tested in
    `test_overrides.py`, exercised only through the HTTP contract in
    `test_overrides_api.py`; needed by V2-GREEN's ambiguous-upload path.
  - `resolve_pending(pending_id: str, key: str) -> None` — assigns pending
    content to `key` and enables it.

  **Settled `/admin/api/overrides*` contract for V2-GREEN:**
  - `POST /admin/api/overrides` (multipart, field name `file`) -> one
    candidate: 200 `{"status": "matched", "endpoint": "<key>"}`; multiple:
    200 `{"status": "ambiguous", "candidates": [...], "pending_id": "..."}`;
    zero: 422 `{"status": "unrecognized"}`.
  - `POST /admin/api/overrides/resolve` body
    `{"pending_id": "...", "endpoint": "<key>"}` -> 200 (exact response
    body beyond the status intentionally left unspecified/flexible — RED
    only asserts 200 + the resulting `GET` state).
  - `GET /admin/api/overrides` -> 200, JSON object keyed by endpoint key
    (`filename`, `content_type`, `enabled`, `uploaded_at` per entry).
  - `PUT /admin/api/overrides/{key}` body `{"enabled": bool}` -> 200.
  - `DELETE /admin/api/overrides/{key}` -> 200.

- 2026-09-23: V1/V2-GREEN implemented (delegated direct, one writer).
  `app/overrides.py` created with `detect_candidates`, `detect_content_type`
  (small addition beyond the locked contract — a helper so the admin API can
  determine `"xml"`/`"json"` for storage without re-implementing the parse
  logic; not itself unit-tested, only exercised indirectly through the HTTP
  tests), the `Override` dataclass, and all the settled storage functions
  (`set_override`, `get_active_override`, `list_overrides`, `set_enabled`,
  `delete_override`, `clear_all_overrides`, `store_pending`,
  `resolve_pending`). The 16 fingerprint entries (including the two-variant
  `master_data.addressees` fingerprint for `firstname`/`current_company_name`
  and the 3 ambiguous multi-key groups) were checked pairwise against every
  RED test fixture for accidental cross-matches before running tests — none
  found, and none surfaced during test runs either.

  `app/routers/admin.py` got the 5 new endpoints
  (`POST /admin/api/overrides`, `POST /admin/api/overrides/resolve`,
  `GET /admin/api/overrides`, `PUT /admin/api/overrides/{key}`,
  `DELETE /admin/api/overrides/{key}`) as a pure addition — existing
  settings/CRUD/catalog routes untouched. One implementation note: the
  zero-candidate `422 {"status": "unrecognized"}` response is returned via
  `JSONResponse` directly rather than `HTTPException`, because FastAPI's
  default `HTTPException` handler wraps `detail` as `{"detail": ...}`, which
  would have broken the RED test's `response.json()["status"]` assertion.

  `requirements.txt` got `python-multipart>=0.0.9` (needed for
  `UploadFile`/multipart parsing) and it was installed into `.venv`.

  Test results: `pytest tests/test_overrides.py tests/test_overrides_api.py`
  — 30/30 passed on first run, no iteration needed. Full suite
  `pytest tests/` — **200 passed** (170 base + 30 new), 2 pre-existing
  deprecation warnings only, nothing else changed. No existing test file
  modified; `diagnostics.py`, `master_data.py`, `accounting.py`, `dms.py`
  untouched, per scope. V3 (router integration — actually serving overrides)
  and V4 (frontend UI) remain unchecked, out of scope for this pass.

- 2026-09-23: V3 RED+GREEN implemented (delegated direct, one writer, same
  approach across all 4 router files since it's small and mechanical).

  RED: `tests/test_overrides_integration.py` (9 tests) written first,
  covering the actual payoff behavior end-to-end through the real
  `/admin/api/overrides*` HTTP flow (not by calling `app.overrides`
  directly): `diagnostics.echo`, `master_data.clients` (XML),
  `master_data.banks` (JSON), `accounting.clients` (both XML-override and
  JSON-override cases, confirming the override wins regardless of the
  `Accept` header), one representative endpoint from each of the 3
  ambiguous groups resolved via `/admin/api/overrides/resolve`
  (`accounting.creditors`, `accounting.accounts_payable`,
  `accounting.posting_proposal_rules_incoming`), and `dms.domains`. Ran
  `pytest tests/test_overrides_integration.py -v` and confirmed the correct
  RED signal: all 9 tests failed as assertion failures (uploaded/resolved
  override content stored and enabled correctly via the admin API, but the
  public `GET`s still returned normal generated data), not a collection or
  import error.

  GREEN: wired `overrides.get_active_override("<key>")` into the top of
  every eligible GET handler across `app/routers/diagnostics.py` (1
  handler), `app/routers/master_data.py` (3 handlers — `clients`,
  `addressees`, `banks`; the `addressees/{id}` lookup deliberately skipped,
  per the task doc's exclusion), `app/routers/accounting.py` (16 handlers —
  `clients` plus all 15 fiscal-year sub-resources), and
  `app/routers/dms.py` (2 handlers — `domains`, `documents`) — 22 handlers
  total, matching the endpoint-key table exactly. `accounting.clients`
  checks the override before running its Accept-header content-negotiation
  logic at all, so an active override always wins regardless of the
  request's `Accept` header, per the task doc's explicit design decision.

  One implementation snag found and fixed during GREEN: annotating the
  JSON-returning handlers' return type as `list[dict[str, Any]] | Response`
  (to reflect that they can now return either) broke FastAPI route
  registration at import time — `FastAPIError: Invalid args for response
  field!` — because FastAPI tries to build a Pydantic response model from
  that union and `Response` isn't a valid Pydantic field type. Fix: left
  the return type annotations exactly as they were before (`list[dict[str,
  Any]]`, no `Response` in the union). This is safe and doesn't lie about
  behavior at the framework level: FastAPI has an explicit runtime check
  (`fastapi/routing.py`, `isinstance(raw_response, Response)`) that bypasses
  response-model serialization entirely whenever the actual returned value
  is a `Response` instance, regardless of the declared return-type
  annotation — the same mechanism the pre-existing `accounting.clients` /
  `diagnostics.echo` handlers already relied on with their `-> Response`
  annotations. Confirmed via the failing import to identify the mechanism,
  then via a full green test run to confirm the fix.

  Test results: `pytest tests/test_overrides_integration.py -v` — 9/9
  passed after the router wiring + return-type fix. Full suite
  `pytest tests/ -v` — **209 passed** (200 base + 9 new), same 2
  pre-existing deprecation warnings only, no other changes. No existing
  test file modified.

  Live check (real HTTPS server, port 58452): started
  `uvicorn app.main:app --host 127.0.0.1 --port 58452 --ssl-keyfile
  certs/key.pem --ssl-certfile certs/cert.pem`; uploaded a small custom
  banks JSON file via `curl -sk -F "file=@...;type=application/json"
  https://127.0.0.1:58452/admin/api/overrides` — response
  `{"status":"matched","endpoint":"master_data.banks"}`; then
  `curl -sk https://127.0.0.1:58452/datev/api/master-data/v1/banks`
  returned the uploaded content verbatim (the custom `"LiveCheck Bank"`
  record), not the normal generated banks data. Server stopped via
  `taskkill //F //PID <the actual PID resolved from
  Get-NetTCPConnection -LocalPort 58452>`; confirmed port 58452 free
  afterward.

  Files modified: `app/routers/diagnostics.py`, `app/routers/master_data.py`,
  `app/routers/accounting.py`, `app/routers/dms.py` (override wiring), plus
  the new `tests/test_overrides_integration.py`. No git operations
  performed, per instructions. V4 (frontend UI) and V5 (README + commit)
  remain unchecked, out of scope for this pass.

- 2026-09-23: V4 implemented (delegated direct, one writer, frontend only).

  Added a new "Custom Examples (Overrides)" Bootstrap card to
  `app/routers/admin.py`'s `/admin` page, placed before the existing "API
  Catalog" card, matching the page's established vanilla-JS/Bootstrap-5
  style (no new dependency): a file input (`accept=".xml,.json"`) + "Upload
  & Detect" button posting `FormData` via `fetch` to `POST
  /admin/api/overrides`; result handling for all 3 backend outcomes —
  `matched` shows an `alert-success` "Matched to endpoint: `<key>`. Override
  is now active." and refreshes the table; `ambiguous` renders a radio-button
  choice form among `candidates` with a "Confirm" button that `POST`s
  `{"pending_id", "endpoint"}` to `/admin/api/overrides/resolve`, then shows
  the same success message and refreshes the table; `unrecognized` (422)
  shows an `alert-danger` explaining no matching shape was detected. A table
  (`GET /admin/api/overrides`) lists every stored override (endpoint key,
  filename, content-type badge, uploaded_at, a Bootstrap switch calling `PUT
  .../overrides/{key}` `{"enabled": bool}` to toggle, and a delete button
  calling `DELETE .../overrides/{key}`), with a "No custom overrides
  uploaded yet." empty state, refreshed after every upload/resolve/
  toggle/delete without a full page reload.

  Tests: 3 smoke tests appended to `tests/test_admin_api.py` (matching its
  existing style, after the "follow-on" section) confirming the `/admin`
  page contains the new card heading/id, references the upload endpoint,
  and references the resolve/toggle/delete patterns — reasonable substring
  checks, no brittle exact-markup assertions. No existing test file
  modified (only `app/routers/admin.py` and `tests/test_admin_api.py`
  touched, confirmed via `git status --porcelain`).

  Test results: `pytest tests/ -v` — **212 passed** (209 base + 3 new), same
  2 pre-existing deprecation warnings only.

  Live check (real HTTPS server, port 58452): started uvicorn, confirmed
  `GET /admin` (200) contains `Custom Examples (Overrides)`,
  `id="overrides-card"`, and references to `/admin/api/overrides` and
  `/admin/api/overrides/resolve`. Exercised the real API surface end-to-end
  via curl: uploaded a banks JSON file (`{"status":"matched","endpoint":
  "master_data.banks"}`), confirmed `GET /admin/api/overrides` reflected it
  (enabled, filename, content_type, uploaded_at) and the public
  `GET /datev/api/master-data/v1/banks` served the uploaded content
  verbatim; toggled it off via `PUT` and confirmed the public endpoint fell
  back to normal generated data; deleted it via `DELETE` and confirmed the
  listing returned to `{}`. Server stopped via `taskkill //F //PID 24540`
  (the actual reported PID from the uvicorn startup log, not the shell job
  id); confirmed port 58452 free afterward.

  Files modified: `app/routers/admin.py` (new card + JS) and
  `tests/test_admin_api.py` (3 new smoke tests). No git operations
  performed, per instructions. V5 (README + commit) remains unchecked, out
  of scope for this pass.

- 2026-09-23: **V5 — README updated, epic complete.** Independently re-verified 212/212 passing. README changes: bumped badges/counts, added "Five epics complete" summary with a link to this task doc, a new "Custom overrides" section (linked from Contents and from the "Settings & admin UI" section) explaining detection, the 3 honest-ambiguity groups, and the always-wins-over-content-negotiation behavior, updated project structure (added `app/overrides.py`, both missing task docs from the prior two epics that had never been added to the structure listing), added `python-multipart` to the Technology table, and a new roadmap entry for this epic. Also caught and fixed a pre-existing gap while in there: the admin-ui-polish epic's U5–U7 follow-on (auto-open browser, `/docs` link, DATEV doc links — already shipped in commit `0caded5`) had never been reflected in the README roadmap section; added it now. Epic complete — committed and pushed per the standing "commit+push when an epic/phase finishes" instruction.

- 2026-09-23: **Follow-on — API Catalog "View sample data" now shows a Table/Raw tabbed view with syntax highlighting.** Small, understood, single-file frontend change (direct inline route, no new task doc) on top of the V4 catalog work above. Read `app/routers/admin.py`'s existing `fetchSample`/`renderJsonSample`/`buildCatalogEntry` in full before touching anything.

  Change: replaced the old single-view render (Bootstrap table for JSON, `<pre>` for everything else) with two Bootstrap 5 nav-tabs/tab-pane tabs per catalog entry — **Table** (unchanged `renderJsonSample` output for JSON; a "no tabular view — see Raw tab" message for XML/other, reusing the same idea as the old fallback) and **Raw** (the full raw response body, HTML-escaped via the existing `escapeHtml` helper, inside `<pre><code class="language-json">`/`class="language-xml">` chosen from the fetch's actual `Content-Type`, highlighted via `hljs.highlightElement(...)` after insertion). Default active tab: Table for JSON responses, Raw for XML/other — matches each content type's old default view. Added highlight.js 11.11.2 from `cdnjs.cloudflare.com` (`styles/default.min.css`, `highlight.min.js`, `languages/xml.min.js`, `languages/json.min.js` — all 4 URLs verified 200 via curl before use, no guessed version). Still fetch-on-click only, no auto-load. Unique per-entry tab/pane/code element ids are derived by suffixing (`-tab-table`, `-tab-raw`, `-pane-table`, `-pane-raw`, `-code`) the existing per-entry `sampleId` (`catalog-sample-<areaIdx>-<entryIdx>`) that `buildCatalogEntry`/`renderCatalog` already generate — same scheme extended, no new id generator.

  Tests: 3 smoke tests appended to `tests/test_admin_api.py` (after the existing catalog test, matching its style) — `/admin` references the highlight.js CDN + `highlight.min.js`, contains `nav-tabs`/`tab-pane` markup, and still contains the pre-existing `addressees`/`fiscal-years`/`domains` catalog markers. No existing test modified.

  Test results: `pytest tests/ -v` — **226 passed** (223 base + 3 new), same 2 pre-existing deprecation warnings only.

  Live check (real HTTPS server): port 58452 was already in use by the user's own running server, left untouched — started uvicorn on port 58455 instead (`--host 127.0.0.1 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem`). `curl -sk https://127.0.0.1:58455/admin` (200) confirmed all 4 highlight.js CDN URLs, `nav-tabs`/`tab-pane` markup, and the `addressees`/`fiscal-years`/`domains` catalog markers all present. Server stopped via `taskkill //F //PID 26856` (the actual reported listening PID, not the shell job id); confirmed port 58455's TCP listener gone afterward and port 58452 unaffected throughout.

  Files modified: `app/routers/admin.py` (head CDN link, script CDN tags, `fetchSample` rewritten) and `tests/test_admin_api.py` (3 new smoke tests). No git operations performed, per instructions.

- 2026-09-23: **Follow-on — CSV export/import for the CRUD tables + real endpoint URL shown after an override match.** Three small, understood client-side/presentational additions on top of the work above (direct inline route, no new task doc). Read `app/routers/admin.py`'s existing `loadMasterData`/`loadAccounting`/`renderMasterDataRow`/`renderAccountingRow`, the "Add ..." fieldsets, `CATALOG`'s `__CATALOG_JSON__` embedding pattern, and the override upload success handling (`showOverrideUploadResult`/`uploadOverrideFile`/`renderAmbiguousChoiceForm`) in full before touching anything.

  1. **CSV export.** An "Export CSV" button (`#md-export-csv` / `#ac-export-csv`) in each table's card header downloads the currently-loaded record set (reusing `masterDataRecords`/`accountingRecords`, cached by `loadMasterData`/`loadAccounting` — no re-fetch) as `master-data-clients.csv` / `accounting-clients.csv` via a `Blob` + temporary `<a download>` click. Columns = union of every key across all records; any top-level key that holds an object on at least one record (e.g. accounting's `company_data`) is flattened one level to `parent.child` columns (`collectObjectKeys`/`flattenRecord`), leaving those columns empty for rows where that same key is `null`. A small `toCsv(rows)` helper does proper RFC4180 quoting (comma/quote/newline triggers quoting, embedded quotes doubled).

  2. **CSV bulk import.** A new "Import CSV" fieldset next to each table's existing "Add ..." fieldset (file input + button). Parses the file with a matching `fromCsv(text)` helper (RFC4180-aware: quoted fields, embedded commas/quotes/newlines, first row = header, blank/trailing lines skipped). Only the columns the existing single-record add form already supports are used — `Name`/`Number`/`Status`/`Type` for master-data, `Name`/`Number` for accounting; any other column (e.g. `Id`, `company_data.*` from a re-imported export) is silently ignored. `Number` is coerced with the same `parseInt(..., 10) || 0` the existing single-add handlers use. Each row is POSTed individually to the same `MASTER_DATA_URL`/`ACCOUNTING_URL` the single-add buttons already use (factored into a shared `importCsvRows` helper); failures are counted, not fatal to the batch. After all rows: one table refresh + a Bootstrap alert ("Imported N of M rows" / "... (K failed)").

  3. **Override match now shows the real endpoint URL.** Added `OVERRIDE_ENDPOINT_PATHS: dict[str, str]` in `admin.py` (near `CATALOG`, same style, reusing `_EXAMPLE_CLIENT`/`_EXAMPLE_FISCAL_YEAR`/`_EXAMPLE_COST_SYSTEM`/`_FY_PREFIX`) mapping all 22 override-eligible endpoint keys from `app/overrides.py`'s `_XML_ROOT_MAP`/`_FINGERPRINTS` to their real `/datev/api/...` paths, per this doc's endpoint-key table above. Embedded into the page via a new `__OVERRIDE_PATHS_JSON__` placeholder alongside the existing `__CATALOG_JSON__` one. The JS success-match handler (both the direct-match and ambiguous-resolve paths, now sharing one `overrideMatchedResultHtml(key)` helper) appends "Endpoint: `GET https://127.0.0.1:<live-configured-port>/datev/api/...`" plus a clickable `target="_blank"` link, reusing the existing `state.port`/`buildUrl` pattern the catalog's "Copy curl" button already relies on (refactored `buildCurl` to build on a new `buildUrl(path)` helper).

  Tests: 4 smoke tests appended to `tests/test_admin_api.py` (after the existing catalog-tabs tests, matching style) — presence of the export/import button ids and "Export CSV"/"Import CSV" text for both tables, presence of the `toCsv`/`fromCsv` function definitions, and presence of `OVERRIDE_ENDPOINT_PATHS` plus a known real path (`/datev/api/master-data/v1/banks`) in the rendered page. No existing test modified.

  A real bug was hit and fixed during this pass: the Python source is a plain (non-raw) triple-quoted string, so literal `\r`/`\n` typed directly inside the embedded JS (in `toCsv`'s quoting regex, the CSV line-join, and `fromCsv`'s CR/LF branches) were being decoded by Python into actual control bytes instead of surviving as the 2-character JS escape sequences — silently breaking the inline `<script>` block exactly the way `test_admin_page_js_syntax.py`'s docstring warns about. Fixed by doubling the backslashes (`\\r`, `\\n`) so Python emits the literal escape text for the browser's JS parser to interpret; verified via `node --check` on the extracted inline script, plus a standalone Node sanity check of `toCsv`/`fromCsv`/`recordsToCsv` (quoting/escaping round-trip, embedded-newline-in-quoted-field, nested `company_data` flatten with a `null`-parent row, and blank-trailing-line skip all behaved correctly).

  Test results: `pytest tests/ -v` — **230 passed** (226 base + 4 new), including `test_admin_page_js_syntax.py`'s Node-based syntax check running (not skipped — confirmed `node` on PATH), same 2 pre-existing deprecation warnings only.

  Live check (real HTTPS server): port 58452 was already in use by the user's own running server, left untouched — started uvicorn on port 58456 instead (`--host 127.0.0.1 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem`). `curl -sk https://127.0.0.1:58456/admin` (200) confirmed both `Export CSV`/`Import CSV` button ids, `OVERRIDE_ENDPOINT_PATHS`, and `/datev/api/master-data/v1/banks` all present; also confirmed `/docs` (200) and the master-data JSON admin endpoint (200) still work. Server stopped via `taskkill //F //PID 9176` (the actual reported listening PID, not the shell job id); confirmed port 58456's TCP listener gone afterward and port 58452 unaffected throughout.

  Files modified: `app/routers/admin.py` (new `OVERRIDE_ENDPOINT_PATHS` dict + embedding, export/import UI markup, CSV helpers + wiring, override-match URL display) and `tests/test_admin_api.py` (4 new smoke tests). No git operations performed, per instructions. Noted but left untouched: an unrelated pre-existing working-tree diff in `README.md` and a stray `3.9)` file at the repo root were already present before this pass and are not part of this change.

- 2026-09-23: **Follow-on — API Catalog XML Table tab support + bulk folder import for overrides.** Two small, understood client-side additions on top of the work above (direct inline route, no new task doc). Read the full current `app/routers/admin.py` (tab-building `fetchSample`/`renderJsonSample`, the single-file `uploadOverrideFile`/`renderAmbiguousChoiceForm`/`loadOverrides`) before touching anything.

  1. **XML Table tab.** `fetchSample`'s non-JSON branch previously always showed "No tabular view for this content type — see the Raw tab." Added `xmlStripNamespace`/`xmlElementIsNil`/`xmlElementToObject`/`xmlToRecords`/`parseXmlForTable` (client-side, `DOMParser`, no library) that convert a parsed XML document into the same array-of-objects shape JSON responses already produce, then feed it into the existing `renderJsonSample` — no separate XML table renderer. Repeated same-tag root children (`ArrayOfClientResource > ClientResource`, `ArrayOfClient > Client`) become one row per child; a root with no repetition (`Echo`) becomes one row from the root itself, matching `renderJsonSample`'s existing single-object fallback. `i:nil="true"` (checked namespace-stripped, i.e. any attribute whose local name is `nil`) becomes `null`; anything else becomes `.textContent` as a string — conceptually mirroring `app/overrides.py`'s own `_strip_namespace`. Applies uniformly to any non-JSON response the Table tab tries to render, whether it's the mock's own generated XML or an active XML override — driven by actual parseability, not by which code path served it. The Raw tab is untouched.

  2. **Bulk folder import.** Added a second control next to "Upload & Detect" in the same form row: a `webkitdirectory multiple` file input (`#override-folder-input`) + "Import Folder" button (`#override-folder-import-btn`). Refactored the single-upload POST into a shared `postOverrideFile(file)` used by both the existing single-file handler and the new `importOverrideFolder()`, which filters the selected `FileList` to `.xml`/`.json` names (case-insensitive, others silently skipped), POSTs each sequentially (`await` per file, matching CSV import's one-row-at-a-time approach — not parallel), and tallies `matched` (with endpoint keys), `ambiguous`, and `unrecognized` counts. After processing, shows one summary alert in a new `#override-folder-import-result` div, refreshes `loadOverrides()`, and — for any ambiguous files — reuses the exact same `renderAmbiguousChoiceForm` the single-upload flow already has (extended with optional `filename`/`onResolved` params, no second resolution UI) to walk the user through resolving them one at a time via a small `ambiguousQueue`.

  Tests: 2 smoke tests appended to `tests/test_admin_api.py` (after the existing override-endpoint-paths test, matching style) — presence of `function xmlToRecords(`/`function parseXmlForTable(` (proving the conversion logic actually landed, not just that the page loads) and presence of the `webkitdirectory` input, its id, the Import Folder button id, and its label text. No existing test modified.

  Test results: `pytest tests/ -v` — **232 passed** (230 base + 2 new), including `test_admin_page_js_syntax.py`'s Node-based syntax check running and passing (not skipped — `node` confirmed on PATH), same 2 pre-existing deprecation warnings only. Learned from the prior CSV pass's bug: this change needed no backslashes in the inserted JS at all (no regex, no `\r`/`\n` literals), so that specific failure mode didn't apply here.

  Live check (real HTTPS server): port 58452 was already in use by the user's own running server (confirmed via `netstat -ano | grep :58452`), left untouched — started uvicorn on port 58457 instead (`--host 127.0.0.1 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem`). `curl -sk https://127.0.0.1:58457/admin` (200) confirmed `webkitdirectory`, `Import Folder`, `function xmlToRecords(`, `function parseXmlForTable(`, and `override-folder-input` all present. Fetched `https://127.0.0.1:58457/datev/api/master-data/v1/clients` and `.../diagnostics/v1/echo` and traced `xmlToRecords`'s logic against the actual returned XML by hand (via a Python `ET.fromstring` inspection of the same bytes, standing in for a browser): `ArrayOfClientResource`'s 18 `ClientResource` children share one tag with no XML-prefix (bare default `xmlns` re-declaration, matching `xmlStripNamespace`'s no-colon case) → each becomes one row; fields like `Parent`/`membersToSerialize` carry the `i:nil="true"` attribute (`i` bound to the XMLSchema-instance namespace, matching the `nil`-after-colon-stripping check) → correctly map to `null`; `Echo`'s two children (`echo_message`, `id`) have differing tags → falls to the single-root-object branch, producing one row with both fields, mirroring the JSON single-object fallback. Server stopped via `taskkill //F //PID 28288` (the actual reported listening PID from `netstat`, not the shell job id); confirmed port 58457's TCP listener gone afterward and port 58452 unaffected throughout.

  Files modified: `app/routers/admin.py` (folder-import UI markup + JS: `postOverrideFile`, `renderAmbiguousChoiceForm` extended, `isXmlOrJsonFilename`, `showNextAmbiguousFromQueue`, `importOverrideFolder`; XML table JS: `xmlStripNamespace`, `xmlElementIsNil`, `xmlElementToObject`, `xmlToRecords`, `parseXmlForTable`, `fetchSample`'s non-JSON branch) and `tests/test_admin_api.py` (2 new smoke tests). No git operations performed, per instructions.
