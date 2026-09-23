# DATEV Mock — Write endpoints (SQLite-backed) + live request/response observability

## Objective

User request (2026-09-23): investigate which DATEV resources have documented
`POST`/`PUT` operations beyond the 23 read-only endpoints this mock already
serves, implement them, persist written data in a local SQLite database
(surviving restarts — the whole point of choosing SQLite over the project's
existing in-memory-only philosophy), show that stored data in the admin
frontend, and add a professional live request/response log — in the browser
(expandable, color-coded per query type) and mirrored to the CLI/terminal —
plus explicit detection/logging of requests that hit **unregistered**
endpoints (404s) or other errors, so the log surfaces gaps and failures, not
just successful known traffic.

User explicitly chose **full scope** when asked to choose between "only the
7 resources we already model as GET" vs. "all 20 documented write
operations, including 7 brand-new resource types" (2026-09-23,
`AskUserQuestion`) — full scope confirmed.

## Research: write operations found in DATEV's official specs

Extracted 2026-09-23 from the two official OpenAPI 3.0.1 specs bundled in
the internal ELO reference mock's JAR (`C:\Mockup\serve-0.1-generate.jar`,
`main/mockdata/apispec/Accounting-1.5.0.json` and
`main/mockdata/apispec/Client Master Data-1.6.0.json`) — the same source
already used as ground truth for this mock's 20 extended read endpoints
(`odd/tasks/datev-mock-extended-endpoints.md`). This is official DATEV
schema/contract data (field names, types, `required` flags), not real
business data — safe to embed directly in this repo, same precedent as the
existing spec-derived field tables throughout this project's other epic
docs. The ELO reference mock itself does **not** implement any of these
(`examples/DATEV_Mock_Server_Reference.md`: "Add POST and PUT only when
deliberately required by a consumer... not registered by this active
server scenario") — this mock will be the first implementation of any of
them.

**26 write operations across 14 resource families** (this section's own
original count of "20" was wrong — it undercounted creditors/debitors as 2
operations each instead of 3, POST + PUT-list + PUT-by-id; caught during
P4's independent route-count verification against the actual running
app, not just this doc's table — the table below was always correct, only
this summary line was off). Cross-referenced against
which paths also have a documented `GET` (i.e. can round-trip: write then
read back) — all but 5 do:

| # | Resource (path family) | Ops | Has GET? | Group |
|---|---|---|---|---|
| 1 | `fiscal-years/{fy}/debitors` (+ `/{id}`) | POST, PUT (list), PUT (by id) | Yes — already modeled | A |
| 2 | `fiscal-years/{fy}/creditors` (+ `/{id}`) | POST, PUT (list), PUT (by id) | Yes — already modeled | A |
| 3 | `fiscal-years/{fy}/terms-of-payment` (+ `/{id}`) | POST, PUT (by id) | Yes — already modeled | A |
| 4 | `fiscal-years/{fy}/assets/{asset-id}/stocktaking/` | PUT | Yes — already modeled (`assets/stocktakings`) | A |
| 5 | `fiscal-years/{fy}/cost-systems/{cs}/cost-centers/{id}` | PUT | Yes — already modeled | A |
| 6 | `master-data/clients` (+ `/{id}`, `/{id}/responsibilities`) | POST, PUT, PUT | Yes — already modeled | A |
| 7 | `master-data/addressees` (+ `/{id}`) | POST, PUT | Yes — already modeled | A |
| 8 | `fiscal-years/{fy}/cost-systems/{cs}/cost-center-properties/{id}` | PUT | Yes | B |
| 9 | `fiscal-years/{fy}/cost-systems/{cs}/cost-sequences/{id}` (+ `/cost-accounting-records`) | PUT, POST | Yes | B |
| 10 | `fiscal-years/{fy}/various-addresses` | POST | Yes | B |
| 11 | `master-data/employees` (+ `/{id}`) | POST, PUT | Yes | B |
| 12 | `fiscal-years/{fy}/cost-systems/{cs}/internal-cost-services` | POST | **No** (create-only, no list op in spec) | B |
| 13 | `fiscal-years/{fy}/accounting-sequences` | POST | **No** (create-only; distinct from the already-modeled **read-only** `accounting-sequences-processed`) | B |
| 14 | `fiscal-years/{fy}/posting-proposals-incoming-invoices/batch` | POST | **No** | B |
| 15 | `fiscal-years/{fy}/posting-proposals-outgoing-invoices/batch` | POST | **No** | B |
| 16 | `fiscal-years/{fy}/posting-proposals-cash-register/batch` | POST | **No** | B |

Full resolved request-body field tables (types + `required` flags, directly
resolved from the specs' `$ref` schemas) for all 20 operations are in
**Appendix A** below — extracted once, kept here so no phase needs to
re-open the JAR.

## Architecture decisions

1. **SQLite, not a bigger persistence layer.** `app/db.py`, stdlib
   `sqlite3` (no new dependency — consistent with this project's existing
   minimal-dependency philosophy: no ORM, no build step). File
   `datev_mock.db` at project root, **git-ignored** (same precedent as
   `settings.json`) — created on first write, persists across restarts
   (the explicit point of the user's request: SQLite instead of the
   existing in-memory-only pattern).
2. **One generic table, not 12 bespoke schemas.** Given 12 heterogeneous
   resource families and the project's established "match the shape,
   don't over-engineer relational integrity" philosophy (every GET
   response is already a dataclass → dict → JSON/XML projection):
   ```sql
   CREATE TABLE stored_records (
       resource_type TEXT NOT NULL,   -- e.g. "accounting.debitors"
       record_id     TEXT NOT NULL,
       client_id     TEXT,
       fiscal_year_id TEXT,
       data_json     TEXT NOT NULL,   -- the validated record, snake_case
       created_at    TEXT NOT NULL,
       updated_at    TEXT NOT NULL,
       PRIMARY KEY (resource_type, record_id)
   );
   ```
   One small `app/db.py` (`upsert_record`, `get_record`, `list_records`,
   `delete_record`, `reset()`) backs every one of the 20 write endpoints
   uniformly — new resource types (Group B) need a new Pydantic model and
   router wiring, not a new table/migration.
3. **Request-body validation via FastAPI/Pydantic models**, one per
   resource family, built from Appendix A's resolved field tables (real
   spec-derived required/optional flags) — matches this project's existing
   quality bar (every GET response is fully typed) and gives correct
   Swagger UI "Try it out" request bodies, which matters for a mock whose
   whole purpose is manual/integration testing.
4. **Group A GET responses merge SQLite with the existing fake dataset.**
   Writing a new debitor via `POST` must make it appear in a subsequent
   `GET .../debitors` — that round-trip is the entire point of adding
   writes to a mock. Existing fake-generated records stay as they are
   (unaffected); SQLite-stored records for the same resource are unioned
   in. A `PUT` to an id that only exists in the fake dataset creates a
   SQLite override for that id (read path: SQLite record wins over the
   fake one when both share an id).
5. **Group B resources get matching GET routes wherever the spec
   documents one** (11/16 do) — same round-trip principle. The 5 create-
   only operations (all writing generated create-only, no `id`-based `GET`
   documented) still persist via `app/db.py` for admin-UI visibility and
   audit, just without inventing a public `GET` route the real API doesn't
   have.
6. **Live request/response log**: a small ASGI middleware
   (`app/request_log.py`) captures every request (method, path,
   path/query params, request headers of interest, request body preview,
   response status, response body preview, duration) into (a) a bounded
   in-memory ring buffer (e.g. last 1000 entries) queryable by the admin
   page, (b) a `logging`-based line printed to the CLI/terminal on every
   request, and (c) broadcast to any connected Server-Sent-Events (SSE)
   client for the live browser view. SSE (not WebSocket) because this is
   one-directional server→browser push only — simpler, plain HTTP,
   already fits FastAPI's `StreamingResponse`, no new dependency.
7. **Unregistered-endpoint / error detection** is the *same* middleware,
   not a separate system — it already sees every request/response
   regardless of whether a route matched. A response with status `404`
   whose path doesn't match any registered route (distinguished from a
   legitimate, intentional 404 like the addressee-by-id lookup) gets
   flagged `unmatched: true` in the log entry, styled distinctly in the
   UI (e.g. a red "UNMATCHED" badge) and logged at `WARNING` level on the
   CLI, so gaps in mock coverage are visible during manual testing exactly
   as the user asked.
8. **Admin UI**: a new "Live Request Log" card (SSE-fed table, expandable
   rows for full request/response detail, color-coded by HTTP method +
   status-code range, an "UNMATCHED" filter/highlight) and, for each
   newly-writable resource, extend the existing "Editable datasets"
   pattern (or a new comparable card, reusing its CSV import/export
   conventions where it makes sense) to show/edit SQLite-stored records —
   consistent with the existing admin UI's established look and
   conventions, not a new design language.

## Phases

- [x] P1 — Live request/response logging infrastructure: `app/request_log.py`
      middleware (ring buffer + CLI logging + unmatched-route detection),
      SSE stream endpoint, admin UI "Live Request Log" card (expandable,
      color-coded). Foundational and independent of P2-P3 — built first so
      it's available to help verify every later phase's new endpoints.
- [x] P2 — SQLite core (`app/db.py`, schema, generic CRUD helpers) + Group
      A write endpoints (7 resource families, all already GET-modeled):
      debitors, creditors, terms-of-payment, stocktaking, cost-centers,
      master-data.clients (+ responsibilities), master-data.addressees.
      GET responses updated to merge SQLite-stored records. Admin UI shows
      stored records per resource.
- [x] P3 — Group B new resources (7 families, no prior GET modeling):
      cost-center-properties, cost-sequences (+ cost-accounting-records),
      various-addresses, employees, internal-cost-services,
      accounting-sequences (create), posting-proposals batch (incoming/
      outgoing/cash-register). New Pydantic + dataclass models per
      resource from Appendix A's field tables, SQLite-backed, GET routes
      where the spec documents one, admin UI visibility for all.
- [x] P4 — Full regression + README/task-doc updates (new SQLite
      persistence behavior — a real deviation from this project's
      previously-universal "everything in-memory, reset on restart"
      philosophy, must be documented clearly; live log + unmatched-route
      detection; the 26 new write endpoints).
- [x] P5 — Commit + push per phase (established workflow).

## Route

Every phase: delegated direct (each touches many files — models, db layer,
routers, admin.py, tests — well over the Writer trigger). Orchestrator
verifies live and commits after each phase, same discipline as every prior
epic in this project.

## Progress

- 2026-09-23: Feature doc created. Research done (this doc's own research
  section + Appendix A). User confirmed full scope (Group A + B) via
  `AskUserQuestion`.
- 2026-09-23: P1 done (RED+GREEN, delegated direct). New `app/request_log.py`
  (ring buffer, pub-sub for SSE, CLI logging via stdlib `logging`), an ASGI
  middleware wired in `app/main.py`, `GET /admin/api/logs` (plain JSON) and
  `GET /admin/api/logs/stream` (SSE) in `app/routers/admin.py`, plus a new
  "Live Request Log" admin UI card (expandable rows, color-coded by
  method/status, `UNMATCHED` highlighting, client-side path/error filter).
  289/289 tests passing (276 + 13 new). No dependency added.
  - **Response-body capture**: drains `call_next()`'s `body_iterator` fully
    then rebuilds an equivalent `Response` — verified byte-for-byte via a
    live `Content-Length` check against `accounting/v1/clients`'s real XML
    body (67971 bytes, exact match). `text/event-stream` responses are
    detected and passed through unbuffered (the SSE endpoint's own
    response), avoiding a deadlock a naive "buffer everything" approach
    would cause.
  - **Unmatched-vs-legitimate-404 distinction** (the specific behavior the
    user asked for): verified live — `GET .../addressees/does-not-exist`
    (a real route, business-logic 404) logs `route_path` resolved and
    `unmatched: false`; `GET /datev/api/totally-made-up` (no matching
    route) logs `route_path: null` and `unmatched: true`, and is logged at
    `WARNING` with an `[UNMATCHED]` marker on the CLI (vs `INFO` for
    everything else) — confirmed directly in the server's own stdout.
  - **Live SSE push** verified end-to-end: opened the stream, fired a new
    request from a second terminal, confirmed the new entry arrived over
    the open connection without polling.
  - Browser-based visual verification of the admin card was attempted but
    not possible in this environment — the browser automation tool runs
    in a different network context than the shell tools and can't reach a
    server bound to `127.0.0.1` by the shell (`ERR_CONNECTION_REFUSED`
    from Chrome while `curl` reaches the same port fine). Verified via
    direct HTML inspection instead (`curl`'d the admin page, confirmed the
    "Live Request Log" card markup and `EventSource`/`logs/stream` wiring
    are present) plus the full curl/SSE/CLI verification above.
  - `tests/test_admin_page_js_syntax.py` (the project's standing
    apostrophe-bug regression guard) re-confirmed passing independently.
  - `.gitignore` untouched (no `datev_mock.db` yet — that's P2).
- 2026-09-23: P2 done (RED+GREEN, delegated direct). SQLite core
  (`app/db.py`, single generic `stored_records` table, short-lived
  per-call connections) + 15 write routes across the 7 Group A resource
  families (debitors/creditors: POST + PUT list + PUT by id each;
  terms-of-payment: POST + PUT by id; stocktaking: PUT; cost-centers: PUT;
  master-data.clients: POST + PUT + PUT responsibilities; addressees:
  POST + PUT). New `app/write_models.py` (Pydantic request-body models,
  kept separate from `app/models.py`'s read-side dataclasses on purpose).
  324/324 tests passing (289 + 35 new).
  - **Route count note**: the feature doc's phase description said "13"
    routes; the doc's own detailed per-resource enumeration always listed
    15 (creditors/debitors each have 3 operations, not 2, plus the new
    `responsibilities` sub-resource) — implemented per the detailed
    enumeration, 15 routes, not the summary count. Corrected here for the
    record.
  - **GET-merges-SQLite verified live** (real server, real `datev_mock.db`
    file, not just `TestClient`): POST'd a debitor, a master-data client,
    and a term-of-payment; confirmed each appeared in its resource's `GET`
    in both JSON and XML. **Persistence-across-restart also verified
    live** — killed the server process entirely and started a fresh one
    against the same `datev_mock.db` file; both written records were
    still there. This was the explicit point of choosing SQLite over this
    project's prior in-memory-only philosophy, and it now demonstrably
    works, not just by design.
  - `.gitignore`: confirmed only 4 lines added (`datev_mock.db` +
    `-journal`/`-wal`/`-shm` sidecar files), every pre-existing line
    untouched and in order (`git diff` reviewed directly).
  - `tests/test_admin_page_js_syntax.py` re-confirmed passing
    independently.
  - Nested object/array fields with no dedicated XML rendering
    (`Creditor`/`Debitor`'s `natural_person`/`legal_person`/`addresses`/
    `banks`/`communications`/`accounting_information`) are force-nilled in
    the merged XML/JSON `GET` view specifically (would otherwise render
    as a broken Python `repr()` string inside XML) — full fidelity of
    whatever was actually written stays visible via the new
    `/admin/api/stored-records` endpoint and admin UI card.
  - Full pass count and design-choice detail in the P2 delegated agent's
    report (not duplicated here) — orchestrator independently re-ran the
    full suite (324/324), re-verified `.gitignore`, and live-tested the
    round-trip + restart-persistence behavior directly before committing.
- 2026-09-23: P3 done (RED+GREEN, delegated direct). All 7 Group B
  resources implemented, reusing `app/db.py`'s existing generic
  persistence (zero schema/CRUD changes needed): `cost-center-properties`,
  `cost-sequences` (+`cost-accounting-records`), `various-addresses`,
  `employees` all got a full GET+write vertical slice (new `app/models.py`
  dataclasses, JSON-only — no XML, correct default for a brand-new
  resource with zero real capture evidence); `internal-cost-services`,
  `accounting-sequences` (create — kept deliberately distinct from the
  existing read-only `accounting_sequences_processed`), and the 3
  `posting-proposals-*/batch` endpoints are POST-only, matching the
  spec's own lack of a GET for those 5 operations — no route invented
  where none exists. 344/344 tests passing (324 + 20 new).
  - **`.gitignore` and `app/db.py`/`app/routers/admin.py` untouched** —
    the generic `stored_records` table and the P2 "Stored records" admin
    card needed zero changes to support 7 brand-new resource types,
    confirming architecture decision #2's bet on one generic table over
    bespoke per-resource schemas.
  - **405 vs. unmatched, verified live**: a `GET` on a POST-only path
    (e.g. `internal-cost-services`) correctly returns `405 Method Not
    Allowed` (a real, matched route, just the wrong verb) and P1's
    middleware correctly logs it with `unmatched: false` — distinct from
    both a genuinely unregistered path (`unmatched: true`) and a
    legitimate business-logic 404. Re-verified independently (not just
    trusting the delegated agent's report): `POST` an
    `internal-cost-service`, confirmed `GET` on the same path returns
    `405`, confirmed `/admin/api/logs` shows `unmatched: false` for it.
  - **Round-trip re-verified independently** for `employees` (POST →
    appears in `GET` list and `GET .../{id}`; unknown id still correctly
    404s) and confirmed both new create-only resource types
    (`accounting.internal_cost_services`, `master_data.employees`) appear
    automatically in `/admin/api/stored-records` with no admin-UI code
    changes needed.
  - No fake seed data added for any of the 7 — deliberately kept
    lightweight per the task's own guidance; every one of these resources
    only shows what a caller has actually written, which is arguably more
    honest for write-first resources than inventing fake defaults nobody
    asked for.
- 2026-09-23: P4/P5 done (full regression + README updates + this epic's
  final commit). `pytest tests/ -v` → 344/344, unchanged from the P3
  count (no code changes this phase, docs only).
  - **Precise route inventory, independently verified twice** (once by
    the delegated P4 agent, once again directly by the orchestrator via a
    fresh `app.routes` introspection script — this FastAPI version wraps
    included routers in `_IncludedRouter`, requiring an `original_router`
    unwrap to enumerate correctly, a real gotcha worth remembering for any
    future route-counting): **79 total routes** — 4 framework
    (`/docs`/`/redoc`/`/openapi.json`), 20 admin (17 pre-existing + 3 new:
    `/admin/api/logs`, `/admin/api/logs/stream`,
    `/admin/api/stored-records`), 55 under `/datev/api` (29 `GET` = 23
    original + 6 new Group B list/detail routes, plus 26 write routes = 13
    `POST` + 13 `PUT` = 15 Group A + 11 Group B). All numbers reconcile
    exactly (23+15+11+6+3+4=79 was NOT the check — the correct check is
    29+26=55 datev routes, +20 admin +4 framework =79 — both counts
    confirmed against the live app object, not estimated).
  - **Corrected this doc's own research-section summary line** ("20 write
    operations" → "26") — the per-endpoint table underneath it was always
    right; only the header count was wrong (miscounted creditors/debitors
    as 2 ops each instead of 3). Same class of self-correction this
    project has now made a habit of (W3/W4 in the real-data-reconciliation
    epic did the same for their own doc's claims) — caught by verifying
    against the running system rather than trusting a hand count.
  - **README.md updated**: test badge/count (276→344), a 7th epic entry
    in Status, a new "Write endpoints and persistence" Key Decisions
    subsection (spec provenance, the one-generic-table SQLite rationale,
    the live log's 3-way unmatched/404/405 distinction), and — most
    importantly — every place README previously made a blanket "everything
    resets on restart" claim now explicitly scopes that claim to what it
    still applies to (the 2 admin-editable datasets, custom overrides)
    versus the 26 new write endpoints, which now genuinely persist via
    SQLite. Verified no application code changed this phase (`git status`
    showed only `README.md`).
  - **Live re-verification independently repeated** (not just trusting
    the delegated report): Group A round-trip (creditor), Group B
    round-trip (various-address), a create-only Group B resource's 405 (not
    404) on `GET`, and — the behavior this whole feature was requested
    for — a full server-process kill-and-restart with the same
    `datev_mock.db`, confirming every previously-written record across all
    three resources was still retrievable afterward.
  - This closes the feature: 20→26 write operations (corrected count)
    across 14 resource families, SQLite persistence for them, a live
    browser+CLI request/response log, and unregistered-route/wrong-method
    detection — all implemented, tested (344/344), documented, and
    committed across 4 phases (P1-P4, one commit each).

---

## Appendix A — resolved request-body field tables (spec-derived, structural only)

Format: `field_name (type, required|optional)`. Resolved from the specs'
`$ref` schemas via a one-off script (not re-run per phase — this table is
the durable source of truth). `object`/`array` typed fields are nested
structures (person sub-objects, historical-value arrays, etc.) — resolve
their own sub-schema during implementation of that specific field if/when
it's in scope; most nested shapes already exist in `app/models.py` from
the read-side reconciliation epic (`Creditor`/`Debitor`'s `NaturalPerson`/
`LegalPerson`/`Addresses`/etc., `Addressee`'s `HistoricalValue`) and can be
reused directly for the write-side bodies.

### Group A (already GET-modeled — reuse existing dataclasses' field sets)

**`debitors`/`creditors`** (POST create, PUT list `merge-patch+json`, PUT by id) — same body shape all 3 operations:
`id` (str, optional), `account_number` (int, optional), `accounting_information` (object, optional), `addressee_id` (str, optional), `alternative_search_name` (str, optional), `business_partner_number` (str, optional), `business_partner_relation_id` (str, optional), `caption` (str, optional), `complimentary_close` (str, optional), `correspondence_title` (str, optional), `date_last_modification` (str, optional), `eu_vat_id_country_code` (str, optional), `eu_vat_id_number` (str, optional), `is_business_partner_active` (bool, optional), `is_organization_business_partner` (bool, optional), `legal_entity_type` (str, optional), `salutation` (str, optional), `short_name` (str, optional), `third_party_number` (str, optional), `natural_person`/`legal_person`/`not_specified_person` (object, optional), `addresses`/`communications`/`banks` (array, optional).
Matches `Creditor`/`Debitor` in `app/models.py` almost field-for-field already (built from the same spec family during the extended-endpoints epic) — reuse directly, just add write-path validation (all fields optional per the spec's own `required` flags — DATEV lets you PATCH partial records).

**`terms-of-payment`** (POST create, PUT by id) — same body both:
`id` (str, optional), `caption` (str, **required**), `due_type` (str, optional), `cash_discount1_percentage`/`cash_discount2_percentage` (number, optional), `due_in_days`/`due_as_period` (object, optional). Matches `TermOfPayment` exactly.

**`assets/{asset-id}/stocktaking/`** (PUT) — note this is a *richer* shape than the read-side `AssetStocktaking` model (more fields than currently modeled for GET — the write side of this spec documents fields the read side never showed in any real capture, expected since it's write-only ground truth, not inferred):
`id` (str, optional), `asset_number` (int, **required**), `inventory_number` (str, **required**), `accounting_reason` (int, optional), `general_ledger_account` (object, optional), `inventory_name` (str, optional), `acquisition_date` (str, optional), `economic_lifetime` (int, optional), `kost1_cost_center_id` (str, optional), `branch` (int, optional), `order_date` (str, optional), `origin_type` (str, optional), `price` (number, optional), `quantity` (number, optional), `stocktaking_date` (str, optional), `unit` (str, optional), `farmland_number` (str, optional), `serial_number` (str, optional), `location` (str, optional), `contract_number` (str, optional), `type_of_use` (str, optional), `condition` (str, optional), `isin` (str, optional), `explanation_of_depreciation` (str, optional). Existing `AssetStocktaking` (13 fields) is a strict subset of this — extend it with the new fields (`acquisition_date`, `economic_lifetime`, `branch`, `order_date`, `origin_type`, `farmland_number`, `serial_number`, `contract_number`, `type_of_use`, `isin`, `explanation_of_depreciation`) during P2, all `Optional`.

**`cost-systems/{cs}/cost-centers/{id}`** (PUT):
`id` (str, optional), `properties`/`cost_rates` (array, optional), `creation_date`/`date_last_modification` (str, optional), `email` (str, optional — **new**, not in current `CostCenter`), `long_name`/`short_name` (str, optional), `note` (str, optional — **new**), `postable_from`/`postable_to` (str, optional — **new**), `reference_value` (str, optional — **new**), `responsible` (str, optional). Extend `CostCenter` with `email`, `note`, `postable_from`, `postable_to`, `reference_value` during P2.

**`master-data/clients`** (POST) / **`master-data/clients/{id}`** (PUT) — same body:
`id` (str, optional), `client_since`/`client_to` (str, optional — already modeled, W4), `differing_name` (str, optional — **new**), `legal_person_id` (str, optional), `name` (str, **required**), `natural_person_id` (str, optional), `note` (str, optional — **new**), `number` (int, **required**), `status` (str, optional), `timestamp` (str, optional), `type` (str, **required**), `organization_id`/`organization_name`/`organization_number` (optional — **new**), `establishment_id`/`establishment_name`/`establishment_number`/`establishment_short_name` (optional — **new**), `functional_area_id`/`functional_area_name`/`functional_area_short_name` (optional — **new**). Note: several fields here (`organization_*`, `establishment_*`, `functional_area_*`) were never in this mock's `ClientResource` at all — new optional fields to add.

**`master-data/clients/{id}/responsibilities`** (PUT) — a new sub-resource, array body:
`area_of_responsibility_id`/`area_of_responsibility_name` (str, optional), `employee_id` (str, optional), `employee_display_name` (str, optional), `employee_number` (int, optional), `employee_status` (str, optional), `client_id`/`client_name` (str, optional), `client_number` (int, optional), `client_status` (str, optional), `id` (int, optional). New small model, `ClientResponsibility` — references `employee_id`, so naturally pairs with Group B's new `employees` resource (P3).

**`master-data/addressees`** (POST) / **`.../{id}`** (PUT) — same body:
`id` (str, optional), `eu_vat_id_country_code`/`eu_vat_id_number` (str, optional), `short_names` (array, optional — historical, already modeled W4), `current_short_name` (str, optional), `status` (str, optional), `surrogate_name` (str, optional), `timestamp` (str, optional), `type` (str, **required**), `date_of_birth` (str, optional), `etin` (str, optional), `firstname` (str, optional), `sex` (str, optional), `surnames` (array, optional), `current_surname` (str, optional), `tax_identification_number` (str, optional), `company_names` (array, optional), `current_company_name` (str, optional), `date_of_foundation` (str, optional), `legal_form_ids` (array, optional), `current_legal_form_id` (str, optional), `detail` (object, optional — **new**, not modeled at all — the "detail" sub-object the real-data epic's evidence explicitly noted was never observed in list responses; the write side documents it, so P2 should resolve its sub-schema when implementing), `addresses`/`communications`/`bank_accounts`/`tax_offices`/`contact_persons` (array, optional — mostly **new**, `Addressee` doesn't model these yet). Matches `Addressee` for the historical-array fields (W4) but needs several new optional fields — resolve `detail`'s sub-schema during P2 implementation (truncated in this extraction, re-open the spec file at that point rather than guessing).

### Group B (new resources — no prior GET model, build fresh)

**`cost-systems/{cs}/cost-center-properties/{id}`** (PUT): `id` (str, optional), `characteristics` (array, optional), `description` (str, optional). Small new model, `CostCenterProperty`.

**`cost-systems/{cs}/cost-sequences/{id}`** (PUT): `id` (str, **required**), `accounting_reason` (str, optional), `description` (str, optional), `month` (int, **required**). New model, `CostSequence`.

**`cost-systems/{cs}/cost-sequences/{id}/cost-accounting-records`** (POST): `id` (str, optional), `amount` (number, optional), `account_number` (int, **required**), `alternative_cost_center` (str, optional), `contra_account_number` (int, optional), `cost_center` (str, optional), `date` (str, **required**), `debit_credit_identifier` (str, optional), `document_field1`/`document_field2` (str, optional), `kost_date` (str, optional), `kost_quantity` (number, optional), `text` (str, optional). New model, `CostAccountingRecord`.

**`various-addresses`** (POST): `id` (str, optional), `account_number` (int, optional), `addresses` (array, optional), `business_partner_number` (str, optional), `banks` (array, optional), `caption` (str, optional), `communications` (array, optional), `correspondence_information` (object, optional), `correspondence_title` (str, optional), `date_last_modification` (str, optional), `individual_fields` (array, optional), `legal_entity_type` (str, optional), `legal_person`/`natural_person`/`not_specified_person` (object, optional), `number` (str, optional), `short_name` (str, optional). New model, `VariousAddress` — note this reuses the same person-sub-object shapes already modeled for `Creditor`/`Debitor` (`NaturalPerson`/`LegalPerson`/`NotSpecifiedPerson`), same contract family.

**`master-data/employees`** (POST) / **`.../{id}`** (PUT): `id` (str, optional), `display_name` (str, optional), `email` (str, optional), `entry_date` (str, optional), `fax` (str, optional), `initials` (str, optional), `name` (str, **required**), `natural_person_id` (str, **required**), `note` (str, optional), `number` (int, optional), `phone_extension` (str, optional), `separation_date` (str, optional), `status` (str, optional), `timestamp` (str, optional), `organization_id`/`organization_name`/`organization_number` (optional), `establishment_id`/`establishment_name`/`establishment_number`/`establishment_short_name` (optional), `functional_area_id`/`functional_area_name`/`functional_area_short_name` (optional). New model, `Employee` — same `organization_*`/`establishment_*`/`functional_area_*` field family as `ClientResource`'s new write-side fields above (shared convention across Client Master Data's spec).

**`cost-systems/{cs}/internal-cost-services`** (POST, create-only, no GET): `amount` (number, optional), `cost_center_from` (str, **required**), `cost_center_to` (str, **required**), `document_field1`/`document_field2` (str, optional), `IBLZ_number` (int, optional), `date` (str, optional), `kost_quantity` (number, optional), `month` (str, **required**), `text` (str, optional). New model, `InternalCostService`.

**`fiscal-years/{fy}/accounting-sequences`** (POST, create-only, no GET — distinct from the existing read-only `accounting-sequences-processed`): `accounting_reason` (str, optional), `application_information` (str, optional), `date_from`/`date_to` (str, **required**), `description` (str, optional), `initials` (str, optional), `is_committed` (bool, optional), `record_type` (str, optional), `accounting_records` (array, optional). New model, `AccountingSequenceCreate` (name deliberately distinct from the existing `AccountingSequenceProcessed` to avoid confusion between the read-only processed view and this write-only creation body).

**`posting-proposals-incoming-invoices/batch`** (POST, create-only, no GET): array body, each item: `accounting_transaction_key` (int, optional), `account_number` (int, optional), `amount` (number, **required**), `creditor_account_number` (int, optional), `currency_code` (str, optional), `date` (str, **required**), `delivery_date` (str, optional), `document_field1`/`document_field2` (str, optional), `document_link` (str, optional), `document_system` (str, optional), `goods_and_services` (str, optional), `kost1_cost_center_id`/`kost2_cost_center_id` (str, optional), `name` (str, optional), `posting_description` (str, optional), `tax_rate` (number, optional). New model, `IncomingInvoicePosting`.

**`posting-proposals-outgoing-invoices/batch`** (POST, create-only, no GET): same shape as incoming, but `creditor_account_number` replaced with `debitor_account_number` (int, optional). New model, `OutgoingInvoicePosting`.

**`posting-proposals-cash-register/batch`** (POST, create-only, no GET): `accounting_transaction_key` (int, optional), `amount` (number, **required**), `cash_account_number` (int, **required**), `contra_account_number` (int, optional), `currency_code` (str, optional), `date` (str, **required**), `document_field1`/`document_field2` (str, optional), `document_link` (str, optional), `document_system` (str, optional), `kost1_cost_center_id`/`kost2_cost_center_id` (str, optional), `posting_description` (str, optional), `tax_rate` (number, optional). New model, `CashRegisterPosting`.
