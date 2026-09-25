# Save observed resource responses to disk for later reload (both backends)

## Objective

User request (2026-09-25): "Agregar opción de guardar en una carpeta en
backend con fastapi, o spring-boot todos los requests de un determinado
recurso para que se puedan cargar en el futuro con esos datos si se desea."
— add an option, on both backends, to save all requests/responses for a
given resource to a folder on disk, so that data can be loaded back later
if desired.

**Confirmed with the user (2026-09-25):** save **all distinct variants**
observed for a resource (one file per distinct id/query combination), not
just the latest.

## Design (finalized, grounded in the actual code — not assumed)

**A real correctness bug avoided by reading the code first**: the original
idea was to reuse `app/request_log.py`'s already-captured data directly.
That does NOT work — `LogEntry.response_body_preview` is deliberately
**truncated** (`_PREVIEW_LIMIT`, ~2000 chars, see `_preview()`) for the live
admin log viewer's own purposes; the full response bytes exist only
transiently inside the logging middleware's own request scope and are never
persisted anywhere. Naively "saving from the log" would silently write
truncated, invalid JSON/XML for any real resource list bigger than ~2KB.

**Actual design**: use the request log only to learn *which distinct
(method, path, query_string) combinations were observed* for a resource
(the truncated preview is irrelevant for this — only the method/path/query
fields are needed, and those are never truncated). For each distinct
combination, **re-issue the request server-side** (a same-origin,
self-loopback HTTP call back into the very same running backend) to obtain
a fresh, complete, current response body — this is both correct (no
truncation) and arguably more useful than a stale log copy (it reflects
whatever the resource currently generates, including any overrides already
active). Write each to a file under a new gitignored `snapshots/` folder,
in **exactly the raw body format the existing overrides-upload endpoint
already accepts** (verified: `app/overrides.py`'s `detect_candidates`/
`detect_content_type` work by parsing the uploaded content itself — XML
root tag or JSON field fingerprinting — not by filename convention), so a
saved snapshot is immediately re-usable via the *existing* overrides UI
with zero new loading mechanism needed.

**Self-loopback is safe here, verified, not assumed**: every FastAPI admin
handler in `app/routers/admin.py` is a plain `def` (sync), not `async def`
— FastAPI runs sync handlers in Starlette's threadpool, so a blocking
outbound HTTP call from inside one runs on its own worker thread, not the
event loop; it cannot deadlock waiting on itself. The already-shipped F5
relay (`app/routers/relay.py`) is the exact same shape (sync `def` making a
blocking `requests.request()` call) — direct precedent in this codebase.
Java's `RelayController` is the same story (blocking `HttpClient.send()` in
a plain, non-reactive `@PostMapping` method, Tomcat's thread-per-request
model). Use the *incoming save-request's own* `request.base_url` (Python)
/ scheme+server-name+port (Java) as the loopback target — no new
config/port-discovery needed, and it's correct regardless of which port the
backend actually started on.

## Scope

- [x] **FastAPI**: new `POST /admin/api/snapshots` (body: `{"path_prefix":
  "<resource path or prefix>"}`). Scans `request_log`'s backlog for GET
  entries whose `path` starts with `path_prefix`, deduplicates by path plus
  canonicalized query string (parameter order-insensitive), re-issues each
  via a self-loopback `requests.get`
  against `request.base_url`, writes each full response body to
  `snapshots/<mirrored-path>[__<sanitized-query>].<json|xml>` (content-type
  decides the extension). Returns `{"saved": N, "files": [...]}`. New
  `snapshots/` folder added to `.gitignore` (matching `datev_mock.db`/
  `settings.json`'s existing treatment as gitignored runtime state).
  Scope deliberately limited to **GET** — write/mutation requests aren't
  "a resource to reload as fake data" in the same sense the overrides
  system already covers, and the whole point is closing the loop with that
  existing GET-response-override mechanism.
- [x] **Java**: equivalent `POST /admin/api/snapshots` on `AdminController`
  (or a new small controller, matching existing style), using SB9's
  `RequestLogStore`/`RequestLoggingFilter` (`admin/` package) the same way,
  a self-loopback via `java.net.http.HttpClient` (same pattern
  `RelayController` already established), writing to the same
  `spring-boot/snapshots/` folder (gitignored, mirroring
  `.jdk21-portable/`/`datev_mock.db*`'s existing treatment).
- [x] **Frontend** (`frontend/admin.html`): a small "Save observed
  responses" action — a text input (resource path/prefix) + button,
  sensibly placed (e.g. near the API Catalog card, prefilled from a
  clicked catalog entry's own path as a convenience), wired via `appFetch`
  to whichever backend's `/admin/api/snapshots` endpoint, showing the
  returned save count/file list. Also needs i18n keys (F8's dictionary) and
  should respect the current theme (no new hardcoded colors) — both
  established conventions from the prior epics this touches alongside.
- [x] Strict TDD on both backends (RED before GREEN), this repo's standing
  convention — the self-loopback logic in particular deserves a real test
  proving actual deduplication and actual fresh-content (not stale/
  truncated) bytes land in the written files, using a real local test
  server the same way F5's relay tests did (not a real external target,
  since this loops back to the app itself — use `TestClient`/an in-process
  app instance for the Python test, and the same JDK `HttpServer`-based
  technique F5 used for the Java test, or run the real Spring context on an
  ephemeral port for a true end-to-end proof).

## Route

Delegated direct — touches `app/main.py` (new router registration),
`app/routers/` (new file), Java's admin package, `frontend/admin.html`, and
both `.gitignore` files — well past the Writer trigger. F1-F8 are all
committed and pushed as of 2026-09-25, so there is no longer a live
file-conflict risk with any other in-flight epic; safe to start now.

## Progress (2026-09-25) — done

**Endpoint shape (identical contract on both backends):**
`POST /admin/api/snapshots`, body `{"path_prefix": "<resource path or
prefix>"}` → `{"saved": <int>, "files": [<absolute file paths>]}`. Scans the
request log's backlog for `GET` entries whose `path` starts with
`path_prefix`, deduplicates by path plus canonicalized query string
(parameter order-insensitive), re-issues each
via a real self-loopback HTTP call, and writes each response body verbatim
to `snapshots/<mirrored-path>[__<query-hash>].<json|xml|txt>`. The extension
is decided by the re-issued response's own `Content-Type` header (`xml` if
it contains "xml", `json` if it contains "json", else `txt`).

**Query-string sanitization (identical scheme, independently implemented
per backend — the two hash digests don't need to match each other, only be
internally stable):** split the raw query string on `&`, sort the parts
(so the same params in a different order collapse to the same file), join,
SHA-1 the result, take the first 10 hex chars, prefix with `__`. Empty query
string → empty suffix (no `__` at all). Python: `app/routers/snapshots.py`
`_query_suffix()`. Java: `RequestSnapshotController.querySuffix()`.

**Files:**
- Python: new `app/routers/snapshots.py` (router + `SnapshotRequest` model +
  `_query_suffix`/`_extension_for_content_type`/`_snapshot_file_path`/
  `_distinct_get_variants`/`save_snapshots`); `app/main.py` registers the
  router (gated the same as `admin`/`relay`); `.gitignore` gets a `snapshots/`
  entry (alongside `datev_mock.db`/`settings.json`).
- Java: new `spring-boot/src/main/java/com/elo/datevmock/web/
  RequestSnapshotController.java` (constructor-injects the existing
  `RequestLogStore` bean, reuses `RelayController`'s own `HttpClient`
  construction pattern — HTTP/1.1 forced, no h2c upgrade); no router
  registration needed (`@RestController` auto-detected by component
  scanning, same as every other controller in this package);
  `spring-boot/.gitignore` gets a matching `snapshots/` entry.
- Frontend: `frontend/admin.html` only — a new "Save observed responses"
  mini-section inside the API Catalog card (text input + button + result
  area), a "Save snapshot" button added to every catalog entry's action row
  (prefills the input from that entry's own path), the `buildSnapshotRequestBody`/
  `prefillSnapshotPrefix`/`renderSnapshotResult`/`saveSnapshots` JS functions
  (wired through the existing `appFetch()`/`apiUrl()` helpers — no relay/
  auth/timeout special-casing needed), and 11 new i18n keys × 3 languages
  (`catalog.saveSnapshot` + 10 `snapshots.*` keys) in `en`/`de`/`es`.
- Tests: new `tests/test_snapshots.py` (Python), new
  `spring-boot/src/test/java/com/elo/datevmock/web/RequestSnapshotControllerTest.java`
  (Java).

**Self-loopback proof — Python:** `TestClient` fakes `request.base_url` as
`http://testserver/`, which `requests.get()` cannot actually connect to, so
it can't exercise the real self-loopback path. `tests/test_snapshots.py`'s
`live_server` fixture instead runs the real FastAPI app via `uvicorn.Server`
in a background thread on a real, OS-assigned loopback port; every test
drives it with the real `requests` library end-to-end — the initiating POST
*and* the self-loopback GET it triggers both go over a real socket. This
proved: (1) a response of 31KB+ (`master-data/v1/clients`, XML) — over 15×
`request_log._PREVIEW_LIMIT` (2000 chars) — is saved byte-for-byte identical
to an independent direct GET, i.e. genuinely not the log's own truncated
preview; (2) two distinct query-string variants (`banks?marker=alpha` /
`?marker=beta`) each produce their own file, and a duplicate `alpha` call
does not produce a second file (real dedup, not just "it happens to look
right"); (3) an unobserved resource returns `{"saved": 0, "files": []}`
(HTTP 200), not an error; (4) XML vs. JSON resources get `.xml`/`.json`
correctly. The self-loopback ran on the FastAPI sync-handler-in-threadpool
model exactly as designed — no deadlock, no hang, across every test run.

**Self-loopback proof — Java:** `RelayControllerTest`'s own technique
(`MockMvc` + a local `HttpServer` stub) doesn't apply here — `MockMvc` never
binds a real socket for *this* application, so a self-loopback call through
it would try to connect to a host:port nothing is listening on. Instead,
`RequestSnapshotControllerTest` uses `@SpringBootTest(webEnvironment =
RANDOM_PORT)` — a real embedded Tomcat on a real ephemeral port — and drives
it end-to-end with `TestRestTemplate`: the initiating POST *and* the
self-loopback GET it triggers both go over a real socket. Proved the same 4
properties as the Python suite, plus the missing-`path_prefix` 4xx case.
One real bug was caught and fixed *in the test*, not the implementation:
`TestRestTemplate`'s default `byte[]` `Accept` header advertises JSON ahead
of XML, so an unqualified comparison GET was silently negotiating a
different (smaller) representation than the controller's own self-loopback
call (a bare `java.net.http.HttpClient` request with no `Accept` header at
all, which gets the server's XML default) — fixed by sending an explicit
`Accept: application/xml` on the comparison call so both sides negotiate the
same representation.

**Test counts:**
- Python: RED (stub router, no route/attributes) → all 9 new tests fail
  (5 `AttributeError`, 4 fixture `ERROR`s). GREEN → 9/9 pass. Full suite:
  `386 → 395 passed` (`pytest tests/ -q`, ~29s). No real `snapshots/`
  directory left at the repo root afterward (every test uses a `tmp_path`-
  scoped root via `monkeypatch.setattr(snapshots, "_SNAPSHOTS_ROOT", ...)`,
  with an explicit `shutil.rmtree` in the fixture's `finally` as
  belt-and-suspenders).
- Java: RED (stub controller, no `@PostMapping`/helper methods) → test
  class fails to *compile* (13 "symbol not found" errors) — the strongest
  possible RED signal. GREEN → 9/9 pass. Full suite: `169 → 178 passed`
  (`mvnw.cmd test`, portable JDK 21.0.12.1 bootstrapped for this session
  since no system Java was present — see below). No real
  `spring-boot/snapshots/` directory left afterward (every test uses a
  JUnit `@TempDir`-scoped root via `controller.setSnapshotsRootForTesting(...)`,
  auto-cleaned by JUnit).
- Cross-file pollution note: `RequestLogStore`/`request_log`'s ring buffers
  are process-wide singletons shared across the *entire* test session on
  both backends (by design, matching a real admin's live request log). The
  first draft of the query-variant and extension tests used
  `/datev/api/accounting/v1/clients` as a `path_prefix` — which is also a
  literal *prefix* of many other test files' deeply-nested fiscal-year
  sub-resource calls — and one such accumulated entry produced a Windows
  path over `MAX_PATH` under pytest's own deep `tmp_path`, crashing the
  Python run when the full suite (not just this file) was executed. Fixed
  by choosing leaf resources with no nested GET children for both
  backends' tests (`master-data/v1/banks`, `diagnostics/v1/echo`,
  `dms/v1/documents`) and asserting "at least N" rather than "exactly N"
  where other test files could plausibly add a harmless extra variant.

**Not committed:** no `git add`/`commit`/`push` was run, per instruction —
`git status --porcelain` shows only the intended source/doc changes plus
`spring-boot/.jdk21-portable/` (gitignored, the portable JDK bootstrapped to
run `mvnw.cmd test` in this session, since no system Java 21+ was present).

## Commit-readiness corrections (2026-09-25) — resolved locally

Two parity/correctness defects found during commit preparation are now
covered before the first commit:

1. **Blank prefix parity:** Java already rejected an absent, empty, or
   whitespace-only `path_prefix` with HTTP 422; FastAPI accepted empty and
   whitespace-only strings, unintentionally matching every logged GET for
   the empty case. `SnapshotRequest` now validates that the supplied string
   contains non-whitespace content, producing FastAPI's standard 422 body.
   Python covers both `""` and `"   "`; Java now explicitly covers those two
   established contract cases as well (in addition to its missing-field
   test).
2. **Canonical deduplication:** filename suffixes already normalized query
   parameter order, but the deduplication keys did not. Observing
   `?b=2&a=1` and `?a=1&b=2` therefore re-issued and counted two exports
   while targeting one filename, so the second write overwrote the first and
   `saved` was inflated. Both backends now use the sorted query form as the
   deduplication identity while retaining the first raw observed query for
   the loopback request. A unique unknown route proves `saved == 1` and one
   returned file for reordered variants, without contamination from the
   process-wide request-log buffer.

**Strict-TDD evidence:** Python RED after adding the regressions:
`pytest tests/test_snapshots.py -q --basetemp=.tmp-pytest-snapshots -p
no:cacheprovider` → **3 failed, 9 passed** (`""` and whitespace returned
200; reordered variants returned `saved: 2`). Python GREEN after the minimal
validation/canonical-identity implementation: the same focused command →
**12 passed** (two non-failing Starlette deprecation warnings). The initial
default pytest invocation could not allocate its sandbox-denied system temp
directory; the workspace-local `--basetemp` is the only runner adjustment.

## Java environment unblocked, RED/GREEN now proven (2026-09-25)

The prior "environment-blocked" note was diagnosed and fixed, not worked
around: `mvnw.cmd` itself has a latent Windows argv-quoting bug — `%~dp0`
(used for `MAVEN_PROJECTBASEDIR`) always ends in a trailing backslash, and
`-Dmaven.multiModuleProjectDirectory="%MAVEN_PROJECTBASEDIR%"` puts that
backslash immediately before the closing quote, which Windows' C-runtime
argv parser treats as an escaped quote — it silently swallows the rest of
the command line (including `org.apache.maven.wrapper.MavenWrapperMain`
itself) into that one property value. This is *not* a Maven or repo
misconfiguration, and `mvnw.cmd` was left untouched (it's Maven's own
generated wrapper script, not this project's code) — the fix lives entirely
in how the JDK/JAVA_HOME and Maven invocation are set up in the calling
shell (a bare `MAVEN_PROJECTBASEDIR` value with no trailing backslash before
the closing quote). The separately-reported "unwritable `C:\.m2`" symptom
was the *default* global repo location colliding with this session's
restricted permissions — routed around with
`-Dmaven.repo.local=<workspace-local path>` (a project-local repo, the same
opt-in pattern this project's own `spring-boot/.gitignore` already
anticipated with its `.m2/` entry — the resolved dependency cache now lives
at `spring-boot/.m2/`, gitignored, not committed).

**Real RED, reproduced by temporarily reverting the two fixes in
`RequestSnapshotController.java`** (removing `.isBlank()` from the
`path_prefix` guard, and using the raw, non-canonicalized query string as
the dedup identity): `mvnw.cmd -Dmaven.repo.local=spring-boot/.m2
-Dtest=RequestSnapshotControllerTest test` → **`Tests run: 11, Failures: 2`**
(the blank/whitespace-prefix test expected HTTP 422 and got 200; the
reordered-query-parameter test expected `saved: 1`/1 file and got 2) — the
exact two regressions the corrections above were written to catch.

**Real GREEN after restoring the implementation:** the same command →
**`Tests run: 11, Failures: 0`**, `BUILD SUCCESS`.

**Full Java suite, restored implementation:** `mvnw.cmd
-Dmaven.repo.local=spring-boot/.m2 test` → **`Tests run: 180, Failures: 0,
Errors: 0, Skipped: 0`**, `BUILD SUCCESS` (169 baseline + 9 feature tests +
2 regression tests = 180, matching the Python side's fully-proven count).

`git diff --check` completed successfully; it only reported pre-existing
working-copy LF→CRLF warnings for `.gitignore`, `frontend/admin.html`, and
this document. No commit hash is recorded because no commit has been made.
