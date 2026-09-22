# DATEV Mock — Settings & Admin UI

## Objective
Add a small admin/settings web UI to the existing, working DATEV Desktop API
mock (see [`datev-mock.md`](datev-mock.md) for the base project — RED→GREEN
already complete there, 32/32 tests passing, deployed). This epic adds:

1. **Port setting** — configurable, persisted to a local (git-ignored)
   settings file. Takes effect on next restart (a running `uvicorn` process
   cannot rebind its port live) — the UI must say so.
2. **Default response format for `accounting/v1/clients`** — configurable
   `xml` or `json`, used only when a request's `Accept` header doesn't
   unambiguously request one or the other. Takes effect immediately, no
   restart needed.
3. **Editable fake dataset** — a UI to view/add/edit/remove the mock's
   fictitious master-data and accounting client records directly (not just
   regenerate them at startup).

## Scope / constraints
- No real DATEV data — same constraint as the base project.
- Must not break any of the 32 existing tests.
- **Critical test-isolation constraint**: the settings file must be
  monkeypatchable to a temp path in tests. If tests ever read/write the
  real project-root settings file, a stray local file from manual UI testing
  could silently change what "default format" the existing accounting tests
  see and make the suite order/environment-dependent. The settings module
  must expose its file path as something a test can override (e.g. a
  module-level path variable or a constructor parameter), not a hardcoded
  literal buried in a function body.
- Existing accounting XML/JSON tests must keep passing unchanged: they
  either send an explicit `Accept` header (unaffected by the default-format
  setting) or rely on the current hardcoded default (XML) — confirm which,
  against `tests/test_accounting.py`, before assuming the new setting is
  safe to introduce.
- Keep the frontend simple: one self-contained HTML page (inline CSS/JS,
  no build step, no frontend framework/dependency), served by FastAPI
  itself. Fetch-based calls to a small JSON admin API.
- Data edits are in-memory for the process lifetime (reset to generated
  defaults on restart) plus an explicit "reset to defaults" action in the
  UI — no need to persist edited records to disk (settings like port/format
  persist; fake data content does not, unless this turns out trivial to add
  later).

## Planned architecture
- `app/config.py` — `Settings` (port, default_accounting_format), `load_settings()` / `save_settings()`, file path overridable for tests.
- `app/data_store.py` (or fold into `fake_data.py`) — mutable `DataStore` wrapping the existing generated lists, with list/add/update/delete/reset methods for both resource types. Existing routers (`master_data.py`, `accounting.py`) read from this store instead of the static module-level lists.
- `app/routers/admin.py` — `GET /admin` (HTML page), `GET/PUT /admin/api/settings`, `GET/POST/PUT/DELETE /admin/api/clients/master-data[/{id}]`, `GET/POST/PUT/DELETE /admin/api/clients/accounting[/{id}]`, `POST /admin/api/reset`.
- `accounting.py` router: when `Accept` doesn't clearly pick XML or JSON, consult the live `default_accounting_format` setting instead of a hardcoded default.

## Tasks
- [x] **S0 — RED-phase tests** for `app/config.py` (load/save/override path), the mutable data store (CRUD + reset), and the new `/admin/api/*` endpoints (settings get/put incl. restart-required signaling, clients CRUD, reset). Must not modify any existing test file.
- [x] **S1 — `app/config.py`** + settings persistence, test-overridable path.
- [x] **S2 — Mutable data store** refactor, existing routers updated to read from it (existing 32 tests must still pass).
- [x] **S3 — `app/routers/admin.py`** — settings + CRUD + reset endpoints.
- [x] **S4 — Admin HTML page** — simple settings form (port, default format) + a table/editor for both client lists.
- [x] **S5 — Update `accounting.py`** to use the live default-format setting for ambiguous `Accept` headers.
- [x] **S6 — README update** — documented the admin UI, its URL, settings semantics (live format switch vs restart-required port), the editable-dataset behavior (in-memory, reset on restart), updated project structure, test counts, and roadmap. Done by the orchestrator after GREEN, since the GREEN writer left it out of its assigned scope.
- [x] **S7 — GREEN verification** — full suite green (old 32 + new), live manual check of the admin page in a real running server.

## Route
- S0: delegated direct (multiple new test files).
- S1–S6: delegated direct, one writer (6+ non-trivial files, Writer trigger).
- S7: orchestrator-run verification.

## Progress
- 2026-09-22: Epic created. Base project (datev-mock.md) already GREEN and deployed; this is a follow-on epic, not a continuation of that one.
- 2026-09-22: **GREEN complete.** 77/77 tests passing (32 base + 45 new). Orchestrator independently re-ran the suite (same result) and live-tested beyond what the GREEN writer checked: format switch via `PUT /admin/api/settings` takes effect immediately on ambiguous requests, an explicit `Accept: application/xml` correctly overrides the live JSON default, add/list/reset cycle on master-data confirmed (18→19→18), invalid port (`0`) correctly rejected with 400. README updated (S6) to document the admin UI, settings semantics, and updated structure/roadmap. Epic complete; committed and pushed per the user's standing "commit+push when an epic finishes" instruction.
- 2026-09-22: **S0 RED phase done.** New files: `tests/test_config.py`,
  `tests/test_data_store.py`, `tests/test_admin_api.py`. All three fail on
  collection with `ModuleNotFoundError`/`ImportError` (confirmed via
  `pytest tests/ -q --continue-on-collection-errors`: `32 passed, 3 errors`
  — the pre-existing 32 tests are untouched and still green, all failures
  are import errors on the not-yet-written modules). No file under `app/`
  was changed; no existing test file was modified.

  **Accept-header finding (blocks assuming the new setting is safe without
  checking):** `tests/test_accounting.py`'s XML-path tests (e.g.
  `test_accounting_content_type_is_xml`, `test_accounting_root_tag_matches_datev_contract`)
  call `client.get(ENDPOINT)` with **no headers argument at all** — they do
  **not** send an explicit `Accept: application/xml` header. They rely on
  today's hardcoded fallback in `app/routers/accounting.py`
  (`if "application/json" in accept.lower(): ... else: <XML>`), which
  currently treats "no header" and "explicit `Accept: application/xml`"
  identically (both fall through the same `else` branch — the code has no
  third state today). Only `tests/test_accounting_json.py` sends an
  explicit header (`{"accept": "application/json"}`).
  Consequence for S5: introducing a live "ambiguous → consult
  `default_accounting_format`" branch is safe for the existing suite **only
  because** `Settings.default_accounting_format` defaults to `"xml"` — if
  that default ever changes, `test_accounting.py` breaks. S5 should also
  decide (not yet tested here) whether an *explicit* `Accept:
  application/xml` should keep forcing XML even when the live default is
  `"json"` (i.e. distinguish "explicit xml" from "ambiguous/no header" as
  two different states, matching the epic's own wording "doesn't
  unambiguously request one or the other") — `test_admin_api.py` only
  exercises the ambiguous/no-header case per this task's instructions.

  **Contract decisions settled by the new tests (unambiguous target for
  GREEN):**
  - `app/config.py`: `Settings` dataclass, `port: int = 58452`,
    `default_accounting_format: str = "xml"`. Validation happens on
    **construction** (`__post_init__`/equivalent raising `ValueError`) for
    both bad port range (must be 1–65535) and unknown format (only `"xml"`/
    `"json"` valid) — not bolted on separately inside `load_settings`/
    `save_settings`. Module-level `SETTINGS_PATH: Path`, re-read from the
    module namespace on every `load_settings()`/`save_settings()` call
    (tests do `monkeypatch.setattr("app.config.SETTINGS_PATH", ...)`, which
    only works if the functions look it up dynamically, not via a
    closed-over/default-arg copy). `load_settings()` returns `Settings()`
    defaults when the path doesn't exist (must not raise).
  - Data store: **`app/data_store.py`** (own module, not folded into
    `fake_data.py`) — plain **module-level functions** (not a class/
    singleton object) operating on process-lifetime mutable state seeded
    from `app.fake_data` at import: `list_master_data()`,
    `add_master_data(fields: dict)`, `update_master_data(id, fields: dict)`
    (raises `KeyError` if unknown, partial-merge semantics),
    `delete_master_data(id)` (clean no-op if unknown, never raises),
    and the accounting-client mirrors of all four
    (`list_accounting_clients`, `add_accounting_client`,
    `update_accounting_client`, `delete_accounting_client`), plus one
    `reset()` that restores **both** datasets together to the same
    cardinality `app/fake_data.py` currently produces: **18** master-data
    `ClientResource` records, **8** accounting `Client` records (confirmed
    from `_generate_client_resources(count: int = 18)` /
    `_generate_accounting_clients(count: int = 8)` and their no-arg
    module-level call sites). `add_*` always generates a fresh `Id`
    server-side and ignores/overwrites any `"Id"` key the caller passes in
    `fields`. Existing routers (`master_data.py`, `accounting.py`) must be
    updated in S2 to read from `data_store.list_master_data()` /
    `data_store.list_accounting_clients()` instead of the static
    `CLIENT_RESOURCES` / `ACCOUNTING_CLIENTS` imports.
  - Admin router (`app/routers/admin.py`, mounted in `app/main.py`):
    - `GET /admin` → 200, `text/html`.
    - `GET /admin/api/settings` → 200 JSON `{"port", "default_accounting_format"}`.
    - `PUT /admin/api/settings` → body **requires both fields** (full
      replace, not a partial PATCH). Response 200 with the new settings
      plus **`restart_required: bool`**, true iff the submitted `port`
      differs from the port that was live immediately before this call
      (format changes never set it). Invalid port/format → 4xx, state
      unchanged.
    - `GET/POST/PUT/DELETE /admin/api/clients/master-data[/{id}]` and the
      same for `.../accounting[/{id}]`: POST → 200 or 201 with the created
      record (incl. generated `Id`); PUT on unknown id → **404**; DELETE
      unknown-id behavior is intentionally unspecified/untested at the API
      layer (data-store-level delete is a no-op, so a 200 no-op is the
      natural GREEN choice, but this wasn't asserted at the HTTP layer).
    - `POST /admin/api/reset` → 200, restores both datasets via
      `data_store.reset()`.
  - Test isolation for `test_admin_api.py`: a **local** (not in
    `tests/conftest.py`) `autouse` fixture monkeypatches
    `app.config.SETTINGS_PATH` to a fresh `tmp_path` file per test and calls
    `POST /admin/api/reset` before/after each test. Deliberately did not
    touch `tests/conftest.py` — an eager top-level `import app.config` /
    `import app.data_store` there would break **collection for every other
    test file** (conftest.py loads once for the whole session), not just
    this one; a local fixture keeps the still-missing-module blast radius
    limited to this file's own expected collection failure.
- 2026-09-22: **GREEN phase done (S1–S5, S7).** Implemented `app/config.py`
  (`Settings` dataclass, `SETTINGS_PATH` module global re-read on every call,
  `load_settings`/`save_settings`), `app/data_store.py` (module-level CRUD
  functions seeded from `app.fake_data` at import, `reset()` regenerates both
  datasets via the existing private generator functions), `app/routers/admin.py`
  (settings GET/PUT with `restart_required` signaling, full master-data/
  accounting CRUD, `POST /admin/api/reset`, and the self-contained `/admin`
  HTML page — inline CSS/vanilla JS, no build step/framework), and mounted it
  in `app/main.py`. Updated `app/routers/master_data.py` and
  `app/routers/accounting.py` to read from `app.data_store` instead of the
  static `fake_data` imports. `accounting.py`'s `Accept` handling now has the
  three explicit states from this epic's content-negotiation decision:
  explicit `application/json` (and not xml) → JSON; explicit `application/xml`
  (and not json) → XML; anything else (missing, `*/*`, unrecognized, both) →
  live `config.load_settings().default_accounting_format`, read fresh per
  request (no caching). `.gitignore` gained `settings.json` (runtime local
  state, alongside `.venv`/`certs/*.pem`).
  Full suite: **77 passed** (32 pre-existing + 45 new across
  `test_config.py`, `test_data_store.py`, `test_admin_api.py`), no existing
  test file modified. Live manual check: started uvicorn with the existing
  certs on port 58452, `curl -k https://127.0.0.1:58452/admin` returned 200
  `text/html`, `GET /admin/api/settings` returned the live JSON settings, and
  `GET /admin/api/clients/master-data` returned 18 records — server stopped
  afterward, confirmed no stray `settings.json` was written at the project
  root (only `GET`s were exercised live, no `PUT`). **S6 (README update) was
  left undone** — it was outside this GREEN pass's assigned scope; the
  README does not yet document the admin UI.
