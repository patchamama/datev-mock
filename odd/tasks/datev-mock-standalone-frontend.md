# Standalone multi-backend admin frontend, real-DATEV connectivity, and endpoint E2E test runner

## Problem and why

Today's `/admin` frontend (a single embedded HTML/CSS/JS page, `_PAGE` in
`app/routers/admin.py`, ~1480 lines, served only by FastAPI at `GET /admin`)
already supports pointing its `fetch()`/SSE calls at a different backend via
a per-browser `localStorage` "API base URL" setting (`loadApiBase()` /
`API_BASE`, added in SB9 of `odd/tasks/datev-mock-spring-boot-migration.md`).
It already has a working `CATALOG` (`app/routers/admin.py:296`, ~40 entries:
`area`/`name`/`path`/`note`/`example_only`) rendered by `renderCatalog()` —
a reference list today, not yet a test runner.

The user wants to go further, in one coherent direction: stop treating this
page as "FastAPI's own admin page that happens to have a base-URL setting",
and treat it instead as **its own standalone app** that can point at *any*
DATEV-compatible target — this project's FastAPI mock, its Spring Boot mock,
or a **real DATEV Desktop API** — with proper connection settings (auth,
protocol, host, port, path prefix, timeouts) and a one-click endpoint
health/E2E check with a progress bar.

## Grounded findings (verified by reading the actual code, not assumed)

- `_PAGE` is a plain triple-quoted Python string, **not** an f-string —
  no server-side Jinja/interpolation happens at request time except two
  literal placeholder swaps done by `admin_page()`
  (`app/routers/admin.py:1879-1882`): `__CATALOG_JSON__` → `json.dumps(CATALOG)`
  and `__OVERRIDE_PATHS_JSON__` → `json.dumps(OVERRIDE_ENDPOINT_PATHS)`. Both
  are fixed, non-request-dependent Python data. This means the page is
  genuinely extractable as a static `.html` file with those two JSON blobs
  baked in at export time (or fetched from a small static JSON file) —
  extraction is a mechanical transform, not a rewrite.
- `API_BASE` is already per-browser (`localStorage`), already used to build
  every URL constant (`SETTINGS_URL`, `MASTER_DATA_URL`, etc.) and the SSE
  `EventSource` URL. The new connection-settings fields below extend this
  existing mechanism; they do not replace it.
- No dedicated auth-header injection exists yet — every `fetch()` call today
  is a bare same-origin-style call with no `Authorization` header and no
  request timeout handling (relies on the browser's own default, which has
  no fixed ceiling).
- `CorsConfig.java` (Java) and FastAPI's `allow_origin_regex` (Python) both
  already allow any `http(s)://localhost|127.0.0.1[:port]` origin — this
  project's own two backends are already fine to call cross-origin from a
  standalone page served from a *different* localhost port. A **real DATEV
  Desktop API is not under this project's control** and is not guaranteed to
  send any CORS header at all (see the open decision below).

## Real technical constraint that shapes the design (verified, not assumed)

Two standard, unavoidable browser-platform facts, not implementation choices:

1. **CORS.** A page's own JS can only read a cross-origin response if the
   *target* server sends `Access-Control-Allow-Origin` matching the page's
   origin. This project's two mock backends already do; a real DATEV
   Desktop API almost certainly does not, and we cannot add CORS headers to
   DATEV's own server. A standalone page opened from `file://` or a small
   static server therefore **cannot reliably call a real DATEV instance
   directly from browser JS** — the browser will block the response
   regardless of how correct the request is.
2. **NTLM.** NTLM is a connection-oriented, multi-round challenge/response
   handshake. Browsers only perform it transparently via **Integrated
   Windows Authentication** using the OS's *currently logged-in* identity —
   there is no browser API to hand `fetch()`/`XMLHttpRequest` an arbitrary
   NTLM username/password pair and have it complete the handshake as that
   user. A from-scratch JS NTLM client is possible in principle (MD4/HMAC-MD5
   via WebCrypto) but needs a persistent, request-correlated TCP connection
   across the 401 → Type2 → Type3 round trip that `fetch()` does not expose
   or guarantee — this is why no mainstream browser-JS NTLM client library
   exists for arbitrary credentials.

**Consequence:** a purely client-side standalone page can support Basic auth
against a CORS-friendly target directly, but **cannot**, by itself, reliably
support NTLM or an arbitrary real-DATEV target that lacks CORS. Making both
of those actually work (which the user's own settings list explicitly asks
for: "Auth: Basic/NTLM" against "diferentes DATEV") requires a small local
relay that the standalone page talks to same-origin/CORS-friendly, which
then makes the real outbound call (including the NTLM handshake, trivial
server-side with standard libraries) to the configured DATEV target. This is
a real architecture fork with a functional consequence (NTLM either works or
silently can't), not a stylistic preference — see the open decision the user
was asked about in this session before implementation started.

## Scope (epics)

- [x] **F1 — Extract the admin frontend into a standalone static app**, kept
  byte-behavior-compatible with today's embedded `/admin` page, servable
  without FastAPI running at all (a plain static file, or a tiny static
  server/script), while FastAPI (and optionally Java) can keep serving the
  same source so nothing regresses for existing users.
- [ ] **F2 — DATEV target connection settings UI**: Auth type (Basic/NTLM),
  protocol (http/https), hostname/IP, port, URL path prefix (with a help
  button showing a worked example), HTTP connect timeout (sec), HTTP read
  timeout (sec) — persisted per-browser alongside today's API-base setting,
  and actually applied to every outbound call (auth header/timeout wiring),
  not just stored.
- [ ] **F3 — `start_java_datev_mock.bat` / `.sh`**: detect an existing Java
  21 install (check the ELO default location first, then other common system
  locations, then `JAVA_HOME`/`PATH`) before falling back to downloading a
  portable, project-local JDK used only by this launcher — never silently
  reinstalling over a perfectly good existing Java.
- [ ] **F4 — Endpoint E2E test runner**: a "Test all endpoints" action in the
  frontend, driven by the existing `CATALOG`, with a progress bar, that
  fires each request against the currently configured backend/target and
  reports pass/fail (status code, or reachability) per endpoint.

## Architecture decision (resolved)

Asked and answered in conversation: **direct browser calls only** — no relay
component for this pass. Concrete consequences, agreed and explicit rather
than a silent limitation:

- F1 ships as a pure static page (no bundled local server).
- F2's Auth-type field includes both "Basic" and "NTLM" in the UI (per the
  user's own settings list), but **NTLM is UI-only for now** — selecting it
  cannot complete a real NTLM handshake from browser JS (see the platform
  constraint above); this must be stated plainly in the field's own help
  text/tooltip, not left to silently fail without explanation.
- A real DATEV Desktop API target only works through this frontend if that
  DATEV instance's own server sends CORS headers allowing the frontend's
  origin — outside this project's control. This project's own two mock
  backends (FastAPI, Java) already send permissive localhost CORS, so they
  work today and will keep working.
- F4's test runner calls targets directly from the browser, same as every
  other feature on the page.
- A local relay to make NTLM/no-CORS targets actually work is explicitly
  **deferred**, not abandoned — it stays a candidate future epic (e.g. F5)
  if the user later decides they need it.

## Delivery

Each epic (F1-F4) is its own reviewable work-unit commit, following this
repo's established TDD-mandatory, evidence-based epic pattern (see
`datev-mock-spring-boot-migration.md` for the house style). Push after each
epic, per the user's own established checkpoint-rhythm preference.

## Epics

### F1 — Extract the admin frontend into a standalone static app

- **Scope:** Move the admin page's HTML/CSS/JS out of the `_PAGE` Python
  triple-quoted string in `app/routers/admin.py` (~lines 403-1876 before this
  change) into a new, genuinely self-contained top-level file,
  `frontend/admin.html`, and make `GET /admin` serve that file's bytes
  instead of building the page at request time.
- **Extraction method (mechanical, not a rewrite):** ran the live module
  in-process — `_PAGE.replace("__CATALOG_JSON__", json.dumps(CATALOG)).replace("__OVERRIDE_PATHS_JSON__", json.dumps(OVERRIDE_ENDPOINT_PATHS))`
  — the exact same substitution `admin_page()` used to perform — and wrote
  the resulting string straight to `frontend/admin.html`. This sidesteps a
  correctness trap: several lines inside `_PAGE` contain Python-source
  double-backslash escapes (`\\r`, `\\n`, e.g. the CSV helpers' `/[",\\r\\n]/`
  regex and `"\\r\\n"` join) that are single backslashes in the actual
  runtime string value; copying the *Python source lines* verbatim instead of
  the *evaluated string* would have doubled those backslashes and silently
  broken the CSV import/export JS. Using the real runtime value guarantees
  the extracted file matches what was actually being served, byte for byte.
- **Baked-in data:** the two runtime placeholders are now literal JS values
  in `frontend/admin.html`: `const CATALOG = [...]` (23 entries) and
  `const OVERRIDE_ENDPOINT_PATHS = {...}` (22 keys), both the exact current
  values of `app/routers/admin.py`'s `CATALOG` (line ~302, after the new
  sync-comment) and `OVERRIDE_ENDPOINT_PATHS` (line ~377) at extraction time.
  No `__CATALOG_JSON__`/`__OVERRIDE_PATHS_JSON__` tokens remain in either
  file (`grep -c` returned `0` in both).
- **`app/routers/admin.py` changes:** removed the `_PAGE` string and its
  request-time `.replace()` calls entirely. Added `FRONTEND_ADMIN_HTML_PATH`
  (`Path(__file__).resolve().parent.parent.parent / "frontend" / "admin.html"`)
  and `_load_admin_page_html()`, which reads the file once and caches it in
  module-level `_ADMIN_PAGE_CACHE` for the process's lifetime (read-once-
  and-cache, not read-per-request — documented in a comment above the
  loader; a process restart is required to pick up hand edits to
  `frontend/admin.html`). `admin_page()` (`GET /admin`, unchanged route path,
  method, and `response_class=HTMLResponse`) now just returns
  `HTMLResponse(content=_load_admin_page_html())`. `CATALOG` and
  `OVERRIDE_ENDPOINT_PATHS` themselves are untouched (still Python source of
  truth, still used server-side by `admin_page()`'s former substitution logic
  — now nowhere in Python — and, per the module docstring, referenced only
  by the JS at runtime; confirmed via `grep -rn CATALOG\|OVERRIDE_ENDPOINT_PATHS app tests` that neither name is used in any other server-side
  validation logic in this repo, so nothing else needed touching).
- **Honest duplication gap (accepted, not silently fixed):** `CATALOG`'s and
  `OVERRIDE_ENDPOINT_PATHS`' Python definitions in `app/routers/admin.py` each
  now carry a `NOTE (F1, ...)` comment stating their current values are
  hand-baked into `frontend/admin.html` and will **not** auto-update if the
  Python values change; `frontend/admin.html` carries a matching `NOTE`
  comment immediately above its `const CATALOG =` line pointing back at
  `app/routers/admin.py`. This is a real, accepted risk: a future edit to
  either Python structure requires a manual re-sync (or regeneration) of
  `frontend/admin.html` until a later epic automates it. F1's job was
  extraction, not building that sync pipeline.
- **Java:** confirmed via `spring-boot/PARITY.md` (line 74: `GET /admin (HTML admin page) | ✓ | absent — by design`) that Java has, and is meant to
  have, no `/admin` HTML route. Left untouched, as instructed.
- **Byte-behavior parity, verified with real evidence:**
  - Captured the pre-change served output in-process (same substitution
    `admin_page()` used to run) as a baseline, 65,680 bytes.
  - Started the real server (`.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 58499 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem`,
    per the README's "Running the server" section, not the one-line
    installer) **after** applying the F1 change, and ran
    `curl -sk https://127.0.0.1:58499/admin`: `HTTP/1.1 200 OK`,
    `content-type: text/html; charset=utf-8`, 66,088 bytes.
  - `diff` of the live response against `frontend/admin.html`: **identical**
    — proves `GET /admin` now serves exactly the static file's bytes, no
    more, no less.
  - `diff` of the live response against the pre-change baseline: the only
    delta is the 6-line `NOTE` comment added above `const CATALOG` (408
    bytes, accounting for the full 65,680 → 66,088 size difference) — a JS
    comment, invisible to the rendered page and inert at runtime. No other
    byte differs; the catalog data, override-paths mapping, settings form,
    master-data/accounting CRUD tables, and every other section render from
    the exact same embedded data as before.
  - Opened/grepped `frontend/admin.html` standalone: valid
    `<!DOCTYPE html>`...`</html>` document, `CATALOG`/`OVERRIDE_ENDPOINT_PATHS`
    literally present as JS array/object data, self-contained (Bootstrap/
    highlight.js via CDN `<link>`/`<script src>` as before — same as the
    original page, no new external dependency), openable via `file://` or
    any static file server with zero backend involvement to render its
    shell.
- **Tests:** `.venv\Scripts\python -m pytest tests/ -q` — **375 passed**, no
  regressions (same count as documented in the README before this change).
  `tests/test_admin_api.py`'s `/admin`-facing assertions (CSV buttons, CSV
  helper functions, `OVERRIDE_ENDPOINT_PATHS` embedding, XML-table
  conversion, etc.) all still pass unmodified against the file-served page.
- **Files touched:** `app/routers/admin.py` (removed `_PAGE`, added
  `FRONTEND_ADMIN_HTML_PATH`/`_load_admin_page_html()`, added the two
  sync-gap `NOTE` comments, rewrote `admin_page()`); new top-level
  `frontend/admin.html` (self-contained static page with baked-in
  `CATALOG`/`OVERRIDE_ENDPOINT_PATHS` and its own `NOTE` comment).
- **Delivery boundary:** One work-unit commit for F1; not committed by the
  implementer per explicit instruction — left for the user's own review and
  commit.
