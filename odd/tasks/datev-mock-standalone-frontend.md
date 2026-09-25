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
- [x] **F2 — DATEV target connection settings UI**: Auth type (Basic/NTLM),
  protocol (http/https), hostname/IP, port, URL path prefix (with a help
  button showing a worked example), HTTP connect timeout (sec), HTTP read
  timeout (sec) — persisted per-browser alongside today's API-base setting,
  and actually applied to every outbound call (auth header/timeout wiring),
  not just stored.
- [x] **F3 — `start_java_datev_mock.bat` / `.sh`**: detect an existing Java
  21 install (check the ELO default location first, then other common system
  locations, then `JAVA_HOME`/`PATH`) before falling back to downloading a
  portable, project-local JDK used only by this launcher — never silently
  reinstalling over a perfectly good existing Java.
- [x] **F4 — Endpoint E2E test runner**: a "Test all endpoints" action in the
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

### F2 — DATEV target connection settings UI

- **Scope:** Replaced the single free-text "API base URL" field in
  `frontend/admin.html`'s "Backend target" card with structured connection
  settings — Protocol (http/https), Hostname/IP, Port, URL path prefix (with
  a help button), Auth type (None/Basic/NTLM), username/password, and
  separate connect/read timeout fields (sec) — all persisted per-browser in
  `localStorage` and actually applied to every outbound call, not just
  stored. Only `frontend/admin.html` was touched, per instruction;
  `app/routers/admin.py`'s `CATALOG`/`OVERRIDE_ENDPOINT_PATHS` were not
  touched since this epic doesn't touch catalog data.
- **URL composition, zero-regression default:** new `composeApiBase(settings)`
  builds `${protocol}://${hostname}${:port}${/prefix}` and returns `""`
  (empty base URL) whenever `hostname` is empty — the exact same
  same-origin, empty-`API_BASE` behavior the page had before this epic. The
  new `CONNECTION_SETTINGS`/`API_BASE` constants feed the same
  `SETTINGS_URL`/`MASTER_DATA_URL`/etc. constants unchanged, so nothing
  downstream needed touching.
- **Backward-compat migration (found necessary, not just nice-to-have):** the
  two existing users of this page may already have a custom base URL saved
  under the old `datevMockApiBase` key (e.g. pointing at the Spring Boot mock
  on `:58553`). Silently ignoring it on first load after this change would
  have been a real regression (their calls would suddenly go to same-origin
  instead of their configured backend). `loadConnectionSettings()` therefore
  does a one-time, best-effort migration: if the new
  `datevMockConnectionSettings` key is absent but the legacy key holds a
  parseable absolute URL, its protocol/hostname/port/path are decomposed
  into the new structured fields (verified round-trip: `composeApiBase()` of
  the migrated fields reproduces the exact original URL — see test below).
- **Auth — Basic is real, NTLM is UI-only (per the resolved architecture
  decision):** `buildAuthHeaders()` adds a genuine
  `Authorization: Basic <base64(user:pass)>` header (UTF-8-safe via the
  `encodeURIComponent`/`unescape` trick, since plain `btoa()` only accepts
  Latin1) only when `authType === "basic"` and a username is set. For
  `authType === "ntlm"`, **no header is ever added and no handshake is
  attempted** — selecting NTLM only shows the same username/password fields
  for UI symmetry plus a persistent inline `alert-warning` (not a tooltip)
  stating plainly that browser JS cannot complete a real NTLM
  challenge/response handshake with an arbitrary credential (no
  `fetch()`/`XMLHttpRequest` API for it; browsers only do NTLM transparently
  via Integrated Windows Authentication using the OS's own logged-in
  identity) and that this option exists for future/manual use only.
- **SSE / `EventSource` cannot carry Basic auth (documented, not silently
  broken):** every `fetch()` call in the page (19 call sites — settings,
  master-data/accounting CRUD, reset, stored records, overrides + CSV
  import, catalog samples) is routed through a new `appFetch()` →
  `fetchWithTimeouts()` pair that injects the auth header and applies both
  timeouts. `connectRequestLogStream()`'s `new EventSource(LOGS_STREAM_URL)`
  is the one exception, called out explicitly in both a code comment above
  it and the card's own help text: the browser `EventSource` API has no
  mechanism to set custom request headers at all, so a configured Basic-auth
  header can never reach the live request-log stream — it only works
  unauthenticated or same-origin, a real browser-platform limitation, not
  something fixable in this page's JS.
- **Connect/read timeout approximation — honest, not exact (documented
  in-code):** browser `fetch()` has no native distinction between "time to
  establish the connection" and "time to read the response body". The
  shared `fetchWithTimeouts(url, options, connectTimeoutSec, readTimeoutSec)`
  helper approximates it with one `AbortController`: one timer, armed for
  `connectTimeoutSec`, covers everything from calling `fetch()` until the
  `Response` resolves (i.e. until headers arrive) — this necessarily also
  covers "waiting for the first response byte", since fetch() cannot expose
  the raw TCP handshake to JS in isolation. Once headers arrive, that timer
  is cancelled and a second `readTimeoutSec` timer is armed via
  `response.body.getReader()`, reset on every chunk actually read from the
  stream, and aborts on any single inter-chunk gap exceeding the limit. A
  multi-paragraph code comment directly above `fetchWithTimeouts()` states
  this is an approximation, not a precise low-level TCP-connect timeout, and
  explains exactly what it can/can't measure — per instruction, this was not
  silently presented as more precise than it is. Every call site was routed
  through it via a thin `appFetch(url, options)` wrapper (not per-call-site
  duplicated timeout logic) that supplies `CONNECTION_SETTINGS.connectTimeoutSec`/
  `readTimeoutSec` from the persisted settings.
- **Help affordance for URL path prefix:** no pre-existing help/info UI
  pattern was found in the page (`grep`'d for `popover`/`tooltip`/`bi-question`/
  modal patterns — none), so a small Bootstrap 5 popover (`data-bs-toggle="popover"`,
  explicit `new bootstrap.Popover(...)` init, since Bootstrap 5 requires
  opt-in per element) was used, consistent with the Bootstrap 5 components
  already used everywhere else on the page. Its content is a concrete worked
  example in English (matching the rest of the page's UI copy, confirmed by
  reading the existing "Backend target"/"Settings" card text before writing
  new copy — not Spanish, despite the source instruction's Spanish example
  text, to stay consistent with the surrounding page).
- **Verification, given the confirmed no-browser-automation constraint for
  this environment (Chrome extension tools cannot reach a locally-bound
  port here, per F1/F3's own session notes):**
  1. Careful direct source read-through of every changed section (HTML card
     markup, the JS settings/compose/auth/timeout helpers, and all 19
     rewritten call sites) for correctness.
  2. Served `frontend/admin.html` with `python -m http.server` from
     `frontend/` and fetched it with `curl` (`HTTP 200`, 79,153 bytes):
     confirmed via script — starts with `<!DOCTYPE html>`, ends with
     `</html>`, zero `__CATALOG_JSON__`/`__OVERRIDE_PATHS_JSON__` leftovers,
     balanced `<script>`/`</script>` (5/5) and `<div>`/`</div>` (145/145)
     tags, no `api-base-input` remnants, new `conn-prefix-help`/
     `fetchWithTimeouts` markers present.
  3. Extracted the page's own inline `<script>` block (58,234 chars) from
     the served output and ran `node --check` on it — exit code 0, proving
     the entire script is syntactically valid JavaScript, not just
     brace/paren-balanced.
  4. Wrote a standalone Node test
     (outside any DOM, per the task's own suggestion) covering exactly the
     pure-logic pieces: `composeApiBase()` (empty-default case, host+port,
     path-prefix slash-stripping, http-without-port), the legacy
     `datevMockApiBase` → structured-fields migration (round-trips to the
     identical original URL), `basicAuthHeaderValue()` (a known
     `admin:secret` → `YWRtaW46c2VjcmV0` base64 vector, empty-password case,
     and a UTF-8 non-Latin1 credential round-trip that would throw with
     plain `btoa()` alone), and `buildAuthHeaders()` (none/ntlm never add a
     header, basic does, basic-with-empty-username doesn't). All 16
     assertions passed.
  5. `.venv\Scripts\python -m pytest tests/ -q` — **375 passed**, identical
     to F1's own baseline; confirms no accidental Python-side regression
     (this epic touched no `.py` file — `git status --porcelain` after the
     change shows only `frontend/admin.html` modified).
- **Files touched:** `frontend/admin.html` only (per instruction) — the
  "Backend target" card markup, the connection-settings load/save/compose/
  auth/timeout JS helpers, the wiring for the new form fields (incl. the
  NTLM warning and auth-fields show/hide), one comment added above
  `connectRequestLogStream()`, and all 19 `fetch()` call sites now routed
  through `appFetch()`.
- **Delivery boundary:** One work-unit commit for F2; not committed by the
  implementer per explicit instruction — left for the user's own review and
  commit.

### F3 — `start_java_datev_mock.bat` / `.sh`

- **Scope:** two new, top-level, Java-specific launcher scripts —
  `start_java_datev_mock.bat` (Windows) and `start_java_datev_mock.sh`
  (Linux/macOS) — that detect a usable Java 21+ install, download a portable
  JDK 21 only if none is found, build `spring-boot/target/datev-mock-*.jar`
  if it doesn't exist yet, and launch it. Neither script touches the
  existing root `start.bat`/`start.sh` (the *Python* FastAPI mock's own
  launchers), `app/routers/admin.py`, or `frontend/` — those are F1's scope,
  worked concurrently by another agent this session.
- **Detection order (both scripts, first hit wins):**
  1. `.bat`: `C:\ELO\java\bin\java.exe` (this project's documented default,
     per `spring-boot/RUNBOOK.md` and `odd/tasks/datev-mock-spring-boot-migration.md`).
     `.sh`: this step is **skipped** — a repo-wide grep for "ELO" + "java"
     mentions across README/RUNBOOK/task docs turned up no equivalent
     well-known default install location documented for Linux/macOS
     anywhere in this repo, so nothing was invented.
  2. `JAVA_HOME` env var, if it points at a working `java`.
  3. `java` resolvable on `PATH` (`where java` / `command -v java`).
  4. Common OS-default locations: Windows `C:\Program Files\Java\*`,
     `C:\Program Files\Eclipse Adoptium\*`, `C:\Program Files\Zulu\*`;
     Linux `/usr/lib/jvm/*`, then `update-alternatives --list java`; macOS
     `/Library/Java/JavaVirtualMachines/*/Contents/Home`, then
     `/usr/libexec/java_home -v 21`.
  Every candidate is version-checked (`java -version`, parsed for major
  version — handles both `"21.0.1"`-style and legacy `"1.8.0_211"`-style
  strings) before being accepted; the first Java **21+** hit in priority
  order wins, not an exhaustive best-of-all-candidates scan, per spec.
- **Portable-JDK fallback (only if nothing above is Java 21+):** downloads
  Eclipse Temurin from the Adoptium API
  (`https://api.adoptium.net/v3/binary/latest/21/ga/<os>/<arch>/jdk/hotspot/normal/eclipse`
  — the "latest" endpoint, not a version-pinned URL, so it won't go stale)
  into the project-local, gitignored `spring-boot/.jdk21-portable/`, reusing
  a previously-bootstrapped one if present. Never touches the system's real
  Java, `PATH`, or `JAVA_HOME` outside the script's own process. Windows
  uses `Invoke-WebRequest`/`Expand-Archive`; `.sh` uses `curl`/`tar` and
  correctly handles the fact that Adoptium's macOS tarball nests the JVM one
  level deeper (`jdk-*/Contents/Home/bin/java`) than Linux's
  (`jdk-*/bin/java`) by searching for `bin/java` after extraction instead of
  assuming a fixed depth.
- **Build step:** if `spring-boot/target/datev-mock-*.jar` doesn't exist,
  builds it first with the resolved Java as `JAVA_HOME`. `.bat` mirrors
  `RUNBOOK.md`'s documented invocation exactly (`.\mvnw.cmd clean package`
  via an explicit relative path, per RUNBOOK's own
  `NoDefaultCurrentDirectoryInExePath` note). **Honest gap:** this repo only
  commits the Windows Maven Wrapper (`spring-boot/mvnw.cmd`); there is no
  committed POSIX `mvnw`/`mvnw.sh`. Rather than shelling out to a
  nonexistent script, `.sh` invokes the same wrapper jar directly
  (`java -classpath .mvn/wrapper/maven-wrapper.jar ... org.apache.maven.wrapper.MavenWrapperMain clean package`),
  which is exactly what `mvnw.cmd` itself does under the hood (confirmed by
  reading `mvnw.cmd`'s own last line), including self-downloading the
  wrapper jar from `maven-wrapper.properties`' `wrapperUrl` if it's missing,
  same as `mvnw.cmd` does.
- **Launch:** `java -jar <jar> --server.port=<port>`, default port `58553`
  (matching `RUNBOOK.md`'s own example port), overridable via `--port PORT`
  or the `DATEV_MOCK_JAVA_PORT` env var — documented in both scripts' own
  `--help`-style usage output and in `RUNBOOK.md`. Both scripts print the
  resolved Java version/path, jar path, and port before launching.
- **Real bug found and fixed during live verification:** the first working
  draft's `check_java_version` used the standard
  `for /f ... in ('"%CANDIDATE%" -version 2^>^&1 ^| findstr ...')` idiom to
  parse `java -version` output. This **failed with a spurious "the filename,
  directory name, or volume label syntax is incorrect" error** and silently
  produced an empty version string, because in `cmd.exe`, `FOR /F`'s
  `('...')` command-string delimiter is a *plain* single quote with no
  special protection from the outer parser — nesting a `"..."`-quoted
  executable path (required for paths containing spaces, e.g.
  `"C:\Program Files\Java\...\java.exe"`) inside it clashes with the pipe/
  redirection escaping needed for the same command string. Reproduced this
  in isolation with a minimal test script before fixing it. **Fix:** redirect
  `-version`'s output to a temp file first, then `for /f` over
  `findstr` against that file — no nested quoting, no pipe, works correctly
  for paths with spaces. This is the actually-shipped implementation.
- **Verified live, on this machine (Windows Server 2022):**
  - Confirmed via `java -version`, `where java`, and `echo %JAVA_HOME%`
    before testing: `C:\ELO\java\bin\java.exe` exists (OpenJDK 21.0.1, Zulu),
    `JAVA_HOME` was unset, and no `java` was on `PATH` — so the ELO-default
    branch was the only real candidate available.
  - Ran `start_java_datev_mock.bat --port 58601` end-to-end: log showed
    `Found Java 21 at C:\ELO\java (this project's ELO default location).`
    with **no download attempted**; found the existing
    `spring-boot/target/datev-mock-0.1.0-SNAPSHOT.jar` (no rebuild needed);
    launched Spring Boot; `curl http://127.0.0.1:58601/actuator/health` →
    `{"status":"UP"}`. Found the bound PID via
    `netstat -ano | grep :58601` (PID 4452) and stopped it with
    `taskkill //PID 4452 //F`; confirmed the port stopped responding
    afterward.
  - Repeated the full run a second time on port `58602` with identical
    result (`Found Java 21 at C:\ELO\java...`, health check `{"status":"UP"}`),
    then stopped it the same way (PID 664).
  - **Fallback-branch verification (inspection-only, clearly labeled):** to
    avoid touching the real environment, made a throwaway copy of the `.bat`
    script with only the ELO-path literal repointed at a nonexistent path
    (`C:\ELO\java_FAKE_NONEXISTENT`), then ran it with `JAVA_HOME` set to a
    nonexistent path and a minimal `PATH` (no `java`). Observed log:
    `No usable Java 21+ install found anywhere on this machine.` →
    `Bootstrapping a portable, project-local JDK 21...` →
    `Downloading portable JDK 21 (x64) from Eclipse Temurin/Adoptium ...` →
    `https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse`.
    This confirms the not-found detection correctly falls through every
    check (including the common-locations scan) and constructs a correct,
    real Adoptium URL for the actual OS/arch (`windows/x64`). The download
    itself was **not completed** — the throwaway test copy's restricted
    `PATH` also removed `powershell.exe`, causing the download call to fail
    immediately (by design, to avoid consuming bandwidth on a real
    multi-hundred-MB JDK download). The real, unmodified script (normal
    `PATH` intact) would proceed to actually download and extract. Deleted
    the throwaway test copy and its log afterward; confirmed the real
    `C:\ELO\java\bin\java.exe` was never touched.
  - `.sh`: **not executed live** in this Windows session (no POSIX shell
    with a real Linux/macOS Java environment available here). Verified by
    careful manual read-through instead: POSIX-compatible syntax throughout
    (`[ ]` tests, no bashisms beyond `local`-style `candidate=`/array-free
    variable use already accepted elsewhere in this repo's own `start.sh`),
    correct `set -e` + `|| true` guarding around pipelines that are allowed
    to fail (version-probing a non-Java binary), no Windows-only assumptions,
    and the same detection order/fallback/port logic as the `.bat` script.
- **Files touched:** new `start_java_datev_mock.bat`, new
  `start_java_datev_mock.sh` (both at repo root, executable bit set on the
  `.sh`); `spring-boot/.gitignore` (added `.jdk21-portable/`);
  `spring-boot/RUNBOOK.md` (new "Recommended: one-command launchers" section
  pointing at these two scripts, ahead of the existing manual build/run
  instructions, which are unchanged and remain valid).
- **Delivery boundary:** One work-unit commit for F3; not committed by the
  implementer per explicit instruction — left for the user's own review and
  commit.

### F4 — Endpoint E2E test runner

- **Scope:** A "Test all endpoints" button in `frontend/admin.html`'s
  existing "API Catalog" card, driving every `CATALOG` entry against the
  currently configured backend (`API_BASE`/`CONNECTION_SETTINGS`, from F2)
  via the existing `appFetch()`/`apiUrl()` helpers, with a live-updating
  Bootstrap progress bar, a results table, and a pass/fail/skipped summary
  line. Only `frontend/admin.html` was touched, per instruction.
- **Placement:** Added directly inside the existing "API Catalog" card,
  right after the `catalog-accordion` div (`frontend/admin.html:324-350`),
  behind an `<hr>` — deliberately reusing the same card rather than adding a
  new one, since the runner conceptually tests exactly what that card
  already lists, and matching the page's existing Bootstrap 5 look (small
  buttons, `table-sm table-striped`, `text-muted small` help copy) instead
  of inventing new visual patterns.
- **Template-only skip logic (belt-and-suspenders, verified against the real
  data):** `isTemplateOnlyEntry(entry)` (`frontend/admin.html:1550-1552`)
  skips an entry when `entry.example_only` is `true` **or** its `path`
  literally contains a `{...}` placeholder, whichever fires first — the
  second check exists in case a future catalog entry gets a template path
  without the flag being set, which would otherwise be fired at the backend
  as a literal, always-404/-400 URL. Extracted and ran the real, baked-in
  `CATALOG` array with Node (`const CATALOG = [...]` at
  `frontend/admin.html:641`, 23 entries) to check both conditions against
  the actual data, not an assumption: **exactly 1 of 23 entries is
  template-only** — `/datev/api/master-data/v1/addressees/{addressee_id}`
  ("Addressee by id") — and it already carries `example_only: true`, so
  both checks agree on every entry today (no silent divergence). The other
  22 entries are real, directly callable GET endpoints and are all tested
  for real.
- **Pass/fail/timeout classification (`testSingleEndpoint()`,
  `frontend/admin.html:1589-1608`):** timed with `performance.now()` around
  `appFetch(apiUrl(entry.path))`.
  - Any HTTP response with `res.ok` (2xx) → **pass**, status text
    `HTTP <code>`.
  - Any HTTP response that resolved but isn't 2xx (4xx/5xx) → **fail**,
    status text `HTTP <code>` (the actual code, not a generic message).
  - `appFetch()`/`fetchWithTimeouts()`'s own `AbortController` firing (its
    connect- or read-timeout elapsing, per F2) rejects with a
    `DOMException` named `AbortError` → **fail**, status text exactly
    `Timeout`.
  - Any other rejection (a real network failure or a CORS block — both
    surface to browser JS as an opaque `TypeError: Failed to fetch`/`Load
    failed` with no further detail, a real browser-platform limitation, not
    a gap in this code) → **fail**, status text
    `Network error / CORS blocked: <err.message>`.
  - A skipped (template-only) entry is never called and is counted
    separately from pass/fail, per instruction ("don't count them as pass
    or fail").
- **Progress bar and live results (`runEndpointTests()`,
  `frontend/admin.html:1617-1652`):** a plain sequential `for` loop —
  `await`s one `testSingleEndpoint()` call at a time, chosen deliberately
  over `Promise.all()`/concurrency so the Bootstrap `.progress-bar`
  (`#test-runner-progress-bar`) advances one visible step per completed
  request (`renderTestRunnerProgress(i + 1, total)`, updating both the width
  style and an `(done/total)` label) instead of jumping from 0% to 100% at
  the end, and so the results table (`#test-runner-results-body`) gets one
  new row appended immediately after each request resolves rather than all
  at once at the end — both requirements from the task were satisfied by
  the same simple loop, no extra buffering/batching needed. A secondary
  reason for staying sequential: firing all 22 requests concurrently would
  hammer whatever backend is currently configured (including a
  hypothetically slow/rate-limited real target) with a burst of 22
  simultaneous requests, which sequential execution avoids.
- **Button disable/re-run:** `runEndpointTests()` guards on a module-level
  `testRunnerRunning` boolean and returns immediately (no-op) if a run is
  already in progress; the button is also `disabled` for the run's duration
  and its label swaps to "Testing…", both restored in a `finally` block so
  the button re-enables even if an unexpected exception escaped
  `testSingleEndpoint()`'s own try/catch. Nothing prevents re-running: the
  user can click "Test all endpoints" again at any time, e.g. right after
  changing F2's connection settings to point at a different backend — each
  run re-reads `CATALOG`/`appFetch`'s live `CONNECTION_SETTINGS` fresh, so a
  new run always tests whatever is currently configured.
- **Summary line:** on completion, `#test-runner-summary` renders
  `"<N> tested — <P> passed, <F> failed, <S> skipped."`, where `tested`
  is deliberately `passCount + failCount` (excludes skipped, per
  instruction's own example wording).
- **Pure client-side, no backend dependency added:** the entire feature is
  client-side orchestration of the already-existing `appFetch()`/`apiUrl()`
  helpers against `CATALOG`, which was already baked into the static file
  since F1 — no new server endpoint, no new network dependency beyond what
  F1/F2 already required. The page remains a genuinely standalone static
  file.
- **Verification, given the same confirmed no-browser-automation constraint
  noted by F1/F2/F3 (Chrome extension tools cannot reach a locally-bound
  port in this environment):**
  1. Extracted the page's single inline `<script>` block from the live file
     and ran `node --check` on it — exit code 0, confirms the whole script
     (including the new F4 code) is syntactically valid JavaScript.
  2. Extracted the real, baked-in `CATALOG` array with Node and counted
     `example_only`/`{...}`-placeholder entries directly against the actual
     data (see above) — **1 template-only entry out of 23**, not assumed or
     estimated.
  3. Wrote a standalone Node unit test (outside any DOM, the same technique
     F2's own agent used for its pure-logic verification) that re-declares
     `isTemplateOnlyEntry()`/`testSingleEndpoint()` verbatim against a fake
     `appFetch` and a small fake `CATALOG`, and asserts: an
     `example_only: true` entry is skipped and never calls `appFetch`; an
     entry with a literal `{...}` path but no `example_only` flag is still
     skipped (proves the belt-and-suspenders rule); a 2xx response is a
     pass; 404 and 500 responses are both fails carrying their real status
     code; an `AbortError` classifies as `"Timeout"`; a generic `TypeError`
     classifies as `"Network error / CORS blocked: <message>"`; and a
     full 5-entry mixed-outcome run produces the correct
     pass/fail/skipped tallies (2/2/1) with `tested = passCount + failCount`
     and a progress sequence that advances monotonically to 100% without
     jumping straight there (`20%, 40%, 60%, 80%, 100%`). **All 16
     assertions passed.**
  4. Attempted the stronger live-server route the task suggested (start the
     real FastAPI mock, drive the extracted `CATALOG`-iteration logic
     against it headlessly from Node) and found it genuinely impractical in
     this environment rather than skipping it by default: this repo has no
     `package.json`/`node_modules` (it is a Python + static-HTML project,
     nothing installs a JS `fetch` polyfill), and the available Node is
     `v16.13.1`, which has no global `fetch()` at all (added in Node 18) —
     so there is no way to run the real `appFetch()` call chain against a
     live server from Node here without installing a new dependency purely
     for this verification step, which was not otherwise warranted. Fell
     back to the explicitly-permitted alternative (step 3 above) instead.
  5. Careful full source read-through of the new DOM/rendering code: button
     disable/enable and label swap (with the `finally`-block restoration),
     progress-bar width/label/`aria-valuenow` updates, live per-row table
     appends via `appendTestRunnerRow()`, and the summary line — confirmed
     against the actual requirements line by line.
  6. Structural sanity checks on the whole file after the edit: `<div>`
     open/close counts balanced (154/154), `<script>` open/close balanced
     (5/5), exactly one each of the new `test-runner-btn`/
     `test-runner-progress-bar`/`test-runner-results-body` ids (no
     duplicate-id bugs), file still starts with `<!DOCTYPE html>` and ends
     with `</html>`.
  7. `.venv\Scripts\python -m pytest tests/ -q` — **375 passed**, identical
     to F1/F2's own baseline; confirms no Python-side regression (this
     epic touched no `.py` file — only `frontend/admin.html` changed).
- **Files touched:** `frontend/admin.html` only (per instruction) — the new
  "Test all endpoints" button/progress bar/results table/summary markup
  inside the existing "API Catalog" card, and the new
  `isTemplateOnlyEntry()`/`renderTestRunnerProgress()`/
  `appendTestRunnerRow()`/`testSingleEndpoint()`/`runEndpointTests()`
  functions placed directly after `renderCatalog()`.
- **Delivery boundary:** One work-unit commit for F4; not committed by the
  implementer per explicit instruction — left for the user's own review and
  commit.

## Current evidence and blockers

- All four epics (F1-F4) touch only their documented files; each epic's own
  write-up above lists the exact files changed and how it was verified.
  `frontend/admin.html` is the one file every epic after F1 modifies (F2's
  connection settings, F4's test runner); F1 created it, F3 is independent
  (new top-level launcher scripts + `spring-boot/RUNBOOK.md`/`.gitignore`
  only).
- Every epic was verified without live browser automation (confirmed
  structurally unavailable in this environment across F1-F4's own session
  notes: the Chrome extension tools cannot reach a locally-bound port here)
  — each epic instead used direct source read-throughs, the real FastAPI
  server + `curl`/Python-side checks where applicable, and standalone Node
  scripts for pure-JS-logic verification (`composeApiBase()`/auth-header
  logic for F2; `isTemplateOnlyEntry()`/`testSingleEndpoint()` classification
  for F4).
- `.venv\Scripts\python -m pytest tests/ -q` has stayed at **375 passed**
  across F1, F2, and F4 (F3 added no Python code) — no epic in this bundle
  introduced a Python-side regression.
- None of F1-F4's commits have been made by the implementing agent(s); each
  epic's changes are left uncommitted for the user's own review, per
  explicit instruction repeated in every epic.

## Next action

**The full epic checklist for this feature bundle (F1-F4) is now complete.**
The admin frontend is extracted into a standalone static file (F1) with
structured, per-browser DATEV connection settings actually wired into every
outbound call (F2), the Java mock has one-command launcher scripts with
Java 21 auto-detection (F3), and the frontend can now E2E-test every
catalog endpoint against whichever backend is currently configured, with a
live progress bar and a pass/fail/skipped summary (F4).

**There is no further planned epic in this bundle.** The one architecture
item explicitly deferred rather than abandoned — a local relay to make
NTLM/no-CORS real-DATEV targets actually work end-to-end (see "Architecture
decision (resolved)" above) — remains a candidate future epic (e.g. F5) only
if the user later decides they need it; it was a resolved, documented
trade-off for this bundle, not an oversight. Any other additional work
starts as its own new epic/decision, not a continuation of this checklist.
