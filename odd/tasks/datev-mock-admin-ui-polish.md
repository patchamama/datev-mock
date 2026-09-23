# DATEV Mock — Admin UI Overhaul & Documentation Polish

## Objective
User request (2026-09-22, Spanish): visually upgrade the `/admin` page with
Bootstrap, turn it into a full catalog covering every mocked endpoint (not
just the 2 CRUD-editable tables), show each table's corresponding endpoint
URL/method and a usable example request, and polish the README to a
professional standard with technology badges. Also record a future task
("port this to a Java app") on the roadmap — documentation only, not
implementation.

## Scope

1. **Admin UI visual redesign** — Bootstrap 5 (CDN), replacing the current
   hand-rolled inline CSS. Keep all existing functionality working exactly
   as before (settings form incl. `restart_required` messaging, master-data
   clients CRUD table, accounting clients CRUD table, reset buttons) — this
   is a redesign, not a rewrite of behavior. `tests/test_admin_api.py`
   (backend JSON contract) must keep passing unchanged.

2. **Full endpoint catalog** — a new section listing every mocked GET
   endpoint (23 total: 1 diagnostics + 2 base clients [already have CRUD
   tables] + 3 Master Data + 15 Accounting sub-resources + 2 DMS), grouped
   by area, each showing: resource name, HTTP method, full path (with
   placeholder path-param values resolved into a real example URL, since
   this mock ignores path-param values by design — see
   [[datev-mock-extended-endpoints]]), a "view sample data" action that
   fetches and renders the live response in a Bootstrap table, and a
   copyable example (`curl` one-liner, using `-k` for the self-signed
   cert). For the 21 read-only resources (everything except the 2 existing
   CRUD tables), the catalog fetches directly from their real public
   `/datev/api/...` endpoint client-side — no new backend endpoints needed,
   since those are already JSON and already live. `echo` (diagnostics) is
   XML and single-object, not a list — show it separately as a small
   "diagnostics ping" card, not a table.

3. **Testing approach (proportional, not full RED/GREEN ceremony)**: this
   phase is overwhelmingly presentational (styling + a client-side catalog
   hitting already-tested, already-working endpoints) with negligible new
   backend logic. Full TDD RED-then-GREEN staging is disproportionate here
   — write a small number of smoke tests (page still 200s, contains
   references to Bootstrap and to a representative sample of the new
   catalog's resource names/paths) alongside the implementation rather than
   as a separate up-front phase. Do NOT skip testing entirely — just keep
   it proportional to the actual risk (near-zero new logic, real risk is
   "did the catalog actually get built and reference real paths").

4. **README polish** — professional structure, technology badges
   (shields.io-style: Python, FastAPI, pytest, Bootstrap, tests-passing
   count), and a new roadmap task: *"Port this mock to a Java
   implementation"* (documentation only — mirrors the tech stack of the
   internal reference mock this project was gap-analyzed against, see
   [[project_internal_java_mock_reference]]). Done by the orchestrator
   directly (well-understood, low-risk documentation work), not delegated.

## Out of scope (explicitly)
- Full CRUD for the 21 extended-endpoint resources — catalog is read-only
  display for those, matching the existing "admin UI CRUD stays limited to
  the original 2 resources unless explicitly requested" decision from the
  extended-endpoints epic. If the user wants full CRUD everywhere later,
  that's a new decision, not assumed here.
- Actually building a Java port — roadmap task only.

## Tasks
- [x] U1 — Admin UI Bootstrap redesign + full endpoint catalog (delegated, one writer)
- [x] U2 — GREEN verification (full suite + live manual check of the new catalog)
- [x] U3 — README professional polish, tech badges, Java-port roadmap task (orchestrator, direct)
- [x] U4 — Commit + push

## Route
U1: delegated direct (large, mostly-presentational rewrite of `app/routers/admin.py`, one writer). U2: orchestrator verification. U3: orchestrator direct edit. U4: orchestrator.

## Follow-on: auto-open browser, /docs link, per-card endpoint display, DATEV doc links (2026-09-22)

User feedback after using the redesigned admin UI:
1. `start.bat`/`start.sh` should auto-open the default browser at `/admin`
   once the server is up.
2. Add a link to `/docs` (Swagger) somewhere visible on the `/admin` page.
3. The Master-data-clients and Accounting-clients CRUD cards don't show
   which real public endpoint they correspond to (the API Catalog entries
   do this, but the two editable cards above it don't) — add it there too.
4. Link to official DATEV documentation per catalog area, where a real one
   is known.

**Confirmed DATEV documentation URLs** (verified live via browser
navigation this session — do not use any URL not listed here, do not
guess/invent one for an area not listed):
- **Master Data** (base `master-data/v1/clients`, `addressees`, `banks`):
  `https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data`
  ("Client Master Data" v1.7.0 — confirmed real product page, lists
  Addressees/Banks/Clients among its resources).
- **Accounting** (base `accounting/v1/clients` + all 15 sub-resources):
  `https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting`
  (confirmed earlier this session, already used to build Phase B).
- **Diagnostics**: no confirmed URL — 3 reasonable slug guesses
  (`diagnostics`, `diagnostics-and-functional-tests`, `functional-tests`)
  all 404'd, and the products-listing toggle UI is too unreliable in this
  session to find it via link discovery either. Leave without a doc link;
  do not guess further.
- **DMS**: no official spec/docs exist at all (already established,
  confirmed by exhaustive search during the extended-endpoints epic) — no
  link, ever, for this area.

## Follow-on tasks
- [x] U5 — `start.bat`/`start.sh`: after the server is confirmed starting,
      auto-open the OS default browser at `https://127.0.0.1:<port>/admin`
      (don't block server startup on this — open the browser a couple
      seconds after launching uvicorn, in parallel, not before).
- [x] U6 — `app/routers/admin.py`: add a `/docs` link (Swagger) to the page
      header/nav; add the real public endpoint (method + path) to the
      Master-data-clients and Accounting-clients CRUD card headers,
      matching how catalog entries already show theirs; add a DATEV
      documentation link to each catalog area/card where a confirmed URL
      exists (Master Data, Accounting), and explicitly no link (not a
      broken/guessed one) for Diagnostics and DMS.
- [x] U7 — GREEN verification (full suite + live check) + commit/push.

### Route (follow-on)
U5/U6: delegated direct (3 files: `start.bat`, `start.sh`,
`app/routers/admin.py` — Writer trigger). Testing proportional to the
original U1 rationale (mostly presentational/config, smoke-test level).
U7: orchestrator.

## Progress
- 2026-09-22: Epic created. Accounting-clients dataset already scaled 8→100 in a separate small commit (`82ab77f`) just before this epic started.
- 2026-09-22: U1+U2 done (delegated writer). Rewrote `app/routers/admin.py`'s
  `_PAGE` to Bootstrap 5.3.3 (CDN CSS + bundle JS): navbar header, settings
  card (unchanged behavior incl. `restart_required` alert), master-data and
  accounting CRUD tables restyled as Bootstrap tables in scrollable
  containers (accounting now holds 100 rows) with Bootstrap-styled
  edit/delete buttons and add-row forms, reset card, and a new "API Catalog"
  card with a Bootstrap accordion grouped by area (Diagnostics, Base
  clients, Master data, Accounting, DMS) covering all 23 mocked GET
  endpoints (verified against `master_data.py`/`accounting.py`/`dms.py`/
  `diagnostics.py`). Each entry shows a GET badge, the real path with
  illustrative path-param values resolved (`example-client-id` /
  `example-fiscal-year-id` / `example-cost-system-id`, called out as
  illustrative-only in a note — this mock ignores path-param values by
  design), an on-demand "View sample data" fetch (JSON renders as a
  Bootstrap table, XML/other renders as a `<pre>` block — this is how the
  diagnostics echo ends up as a single-object "ping" card rather than a
  table, with no special-case code needed) and a "Copy curl" button using
  the live-configured port. The addressee-by-id entry is marked
  "Example only" (path template shown, no live fetch), per the task doc's
  explicit allowance. None of the JSON API contract changed — backend route
  functions in `admin.py` are untouched.
  Testing: added 2 smoke tests to `tests/test_admin_api.py`
  (`test_admin_page_references_bootstrap_cdn`,
  `test_admin_page_contains_full_endpoint_catalog_sample`) — purely
  additive (git diff: `+19/-0`), no existing test modified. Full suite:
  **167 passed** (165 original + 2 new). Live check: started uvicorn for
  real on port 58452 with the project's TLS certs; `GET /admin` → 200;
  confirmed Bootstrap CDN reference and catalog strings
  (`addressees`/`fiscal-years`/`domains`/`example-client-id`) present in the
  raw HTML; spot-checked live endpoints (`diagnostics/v1/echo`,
  `master-data/v1/addressees`, `accounting/v1/clients/example-client-id/
  fiscal-years`, both admin CRUD list endpoints) all 200. Server stopped via
  `taskkill /F /PID <reported "Started server process" PID>`; port verified
  free afterward (a stray leftover uvicorn process from an earlier session
  was found already bound to 58452 before this check and was killed first,
  by its own reported PID, to free the port).

- 2026-09-22: **U3/U4 — README polished, epic complete.** Orchestrator independently re-verified 167/167 passing, then did its own live check beyond U1/U2's: confirmed the client-side `CATALOG` JS array in the raw page HTML has exactly 23 entries (1 diagnostics + 2 base + 3 master-data + 15 accounting + 2 DMS), spot-checked a live Phase-B endpoint via its illustrative example path (`.../example-client-id/fiscal-years/example-fiscal-year-id/creditors` → 200, real creditor JSON) and confirmed the accounting-clients admin table now serves 100 records. README changes: shields.io badges (Python, FastAPI, pytest 167-passing, Bootstrap, status), a table of contents, rewritten "Settings & admin UI" section describing the actual Bootstrap redesign and API Catalog (not the old plain-HTML description), a new "Technology" table, corrected endpoint-count references (20 extended, 23 total — was inconsistently "21"/"24" in places), and a "Planned / not started" section recording the Java-port task (documentation only, not built) plus a note about extending full CRUD to the other 20 resources if ever wanted. All roadmap checkboxes flipped to done. **Epic complete** — committed and pushed per the standing "commit+push when an epic/phase finishes" instruction.

- 2026-09-22: **U5/U6 done (delegated writer).**
  - `start.bat`: introduced a `PORT` variable (`58452`, same value uvicorn
    already used) reused by both the startup echo and the `uvicorn --port`
    flag; added a non-blocking `start "" /min powershell ... "Start-Sleep
    -Seconds 2; Start-Process 'https://127.0.0.1:%PORT%/admin'"` immediately
    before the (unchanged, still-foreground/blocking) uvicorn invocation.
  - `start.sh`: introduced a `PORT=58452` variable reused by the echo and
    `--port` flag; added a backgrounded `( sleep 2; xdg-open "$ADMIN_URL"
    2>/dev/null || open "$ADMIN_URL" 2>/dev/null || echo "Open $ADMIN_URL in
    your browser." ) &` right before the final `exec "$PYTHON_EXE" -m
    uvicorn ...` (background jobs survive `exec` since it only replaces the
    current process image, not its children). `bash -n start.sh` passes.
  - `app/routers/admin.py`: added a `/docs` (Swagger) link/button to the
    navbar; added a small "real endpoint" line under both the
    Master-data-clients and Accounting-clients CRUD card headers (reusing
    the catalog's existing "real endpoint vs. this table's editing
    endpoint" phrasing), each including the exact confirmed DATEV doc URL
    for that area; added an `AREA_DOCS` JS map (`"Master data"` →
    client-master-data 1.7.0 URL, `"Accounting"` → accounting 1.7.4 URL)
    rendered as an "Official DATEV documentation for `<area>`" link at the
    top of each matching accordion group's body. Diagnostics and DMS
    deliberately get no doc link (no confirmed URL exists per the task
    doc) — not present in `AREA_DOCS`, nothing guessed.
  - Exact URLs used (verbatim, matching this doc's "Follow-on" section):
    - Master Data: `https://developer.datev.de/de/product-detail/client-master-data/1.7.0/reference/reference-overview/client-master-data`
    - Accounting: `https://developer.datev.de/de/product-detail/accounting/1.7.4/reference/reference-overview/accounting`
  - Testing: added 3 smoke tests to `tests/test_admin_api.py`
    (`test_admin_page_links_to_swagger_docs`,
    `test_admin_page_contains_confirmed_datev_documentation_urls`,
    `test_admin_page_shows_real_endpoint_on_master_data_and_accounting_cards`)
    — purely additive, appended after the existing tests, no existing test
    modified. Full suite: **170 passed** (167 prior + 3 new).
  - Live check: killed a stray leftover uvicorn already bound to 58452
    (by its own reported PID) before starting; started uvicorn for real on
    58452 with the project's TLS certs; grepped the raw `/admin` HTML:
    `/docs"` link ×1, Master Data DATEV URL ×2 (card header + accordion
    note), Accounting DATEV URL ×2 (card header + accordion note),
    `master-data/v1/clients` ×2, `accounting/v1/clients` ×2; `GET /docs`
    → 200. Server stopped via `taskkill //F //PID <reported "Started
    server process" PID>`; TCP port 58452 verified free afterward (an
    unrelated pre-existing UDP listener on the same port number is not
    uvicorn and was left alone). Auto-open logic itself not visually
    testable in this headless sandbox, per task instructions — script
    logic reasoned through and syntax-checked instead.
  - U7 (commit/push) intentionally left to the orchestrator — this
    delegated writer was instructed not to touch git.

- 2026-09-23: **U7 — orchestrator verification, epic complete.** Independently re-ran the full suite (170/170, matching the writer's report) and did a deeper live check on the actual page content: `curl`'d `/admin` and grepped for all four additions — `/docs` link (1 match), Master Data doc URL (2 matches: card + accordion note), Accounting doc URL (2 matches), `master-data/v1/clients` text (2), `accounting/v1/clients` text (2) — plus confirmed `GET /docs` itself returns 200. All correct.
  **Could not end-to-end test `start.bat` (or `cmd.exe` invocations generally) through this session's tooling**: `cmd.exe /c echo HELLO` and even `cmd /c "cd"` produced no command output at all when run through this Bash tool in this sandbox — a tooling/environment limitation (the harness's handling of a nested native Windows console subprocess), not something in the script itself. This also explains earlier stray artifacts in this project (a `3.9)` debris file from a mangled batch `echo` a few turns back) and a confusing false lead mid-investigation (two unrelated leftover `python.exe` processes found via `wmic` that briefly looked related but weren't reproducible on a clean re-run). Given this, verification fell back to: (1) careful manual review of `start.bat`'s final launch line, confirmed byte-identical to the `uvicorn` invocation already verified working dozens of times this session, (2) the auto-open `PowerShell` snippet tested successfully in isolation (`Start-Sleep` + `Write-Output` dry run), (3) `bash -n start.sh` (already passed, per U5's own report). **Recommended**: the user should test `start.bat`/`start.sh` themselves interactively at least once (double-click or a real terminal, not this sandboxed tool) to confirm the auto-open-browser behavior visually, since that's the one piece this session's tooling couldn't observe directly.
  Epic (including this follow-on) complete — committed and pushed per the standing "commit+push when an epic/phase finishes" instruction.
