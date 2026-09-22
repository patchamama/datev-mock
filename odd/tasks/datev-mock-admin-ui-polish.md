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
