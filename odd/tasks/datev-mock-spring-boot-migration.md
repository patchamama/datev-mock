# Spring Boot parity roadmap

> **Superseded decision (SB0, held through SB3):** `spring-boot/` was a separate Java project with its own initialized `.git` repository. **Merged into this repo after SB3** via `git subtree add --prefix=spring-boot`, commit `82f6cb8`, once the confirmed "same frontend, configurable backend URL" architecture (see the Frontend/backend selection row below) made one root repo the simpler long-term layout for sharing a frontend across both backends. Full history preserved: `32725b1`, `60bbfb2`, `c69666d`, `94d8664` are real ancestors of current `main` (verified with `git merge-base --is-ancestor`). A backup of the pre-merge standalone working tree is kept outside the repo at `C:\Users\eloadmin\spring-boot-standalone-backup` (safe to delete once you're satisfied with the merge). From SB4 onward, Java work commits directly to this repo's own index — no more separate repo, no more `-c safe.directory=...` workaround.

## Remaining path

1. ~~Restore Maven Central availability~~ — done; not a real blocker (see SB1 status).
2. ~~Resume SB1~~ — done.
3. Implement the remaining epics (SB4+) in dependency order, now directly in this repo under `spring-boot/`.
4. Keep every completed epic as a reviewable work-unit commit.

## Contract and boundaries

| Topic | Decision |
| --- | --- |
| Contract source | Current FastAPI code and tests are authoritative. The historical Java JAR/reference is supplementary. |
| Java project | `spring-boot/`, now a normal subdirectory of this repo (merged from its own history-bearing repo after SB3); Java 21 is verified at `C:\ELO\java\bin\java.exe` (Zulu OpenJDK 21.0.1 with `javac` and `jar`). |
| Compatibility | Preserve paths, status codes, request/response shapes, multipart field `file`, XML/JSON negotiation, state semantics, and SSE. |
| Excluded root work | Do not alter existing edits in `.github/workflows/release.yml`, `README.md`, `app/main.py`, or `start.sh`. |
| Delivery | One conventional work-unit commit per coherent epic, in this repo's own index (from SB4 onward); push, PR, and merge remain user decisions. |
| TDD | RED -> GREEN -> REFACTOR is mandatory. No production behavior is claimed without observed evidence. |
| Frontend/backend selection | "Same frontend for both backends" is implemented as a configurable target, not a hardcoded FastAPI/Java switch. The existing `/admin` frontend gains a settings field for the API base URL (scheme+host+port) it talks to; all its API calls go through that configurable base instead of assuming same-origin. Default stays same-origin (today's behavior). This also lets the same frontend point at the real DATEV production API, a DATEV test endpoint, or any other DATEV-compatible mock available locally (e.g. `C:\Mockup\serve-0.1-generate.jar`) for interoperability testing — not just this project's two backends. Scoped into SB9; needs CORS enabled on both this project's backends so cross-origin calls from the frontend's own origin work when the target differs from it. |

The FastAPI inventory contains 29 public GET routes, 25 public POST/PUT routes, and conditionally mounted admin UI/API. Read behavior combines deterministic mock data, SQLite-backed write overlays, content negotiation, overrides, and a request-log SSE stream.

## Dependency-ordered epic checklist

- [x] **SB0 — Bootstrap the standalone repository** *(completed: `32725b1`)*
- [x] **SB1 — Establish build and strict-TDD foundation**
- [x] **SB2 — Shared DATEV contracts, XML, and format negotiation**
- [x] **SB3 — Deterministic mock generation and read-state composition**
- [x] **SB4 — SQLite overlays, validation, and reset semantics**
- [ ] **SB5 — Master-data API parity**
- [ ] **SB6 — Accounting read API parity**
- [ ] **SB7 — Accounting write API parity**
- [ ] **SB8 — DMS and diagnostics parity**
- [ ] **SB9 — Admin frontend/API/settings/override/log/SSE compatibility**
- [ ] **SB10 — Contract-parity and regression verification**
- [ ] **SB11 — Packaging and local runbook**

## Epics

### SB0 — Bootstrap the standalone repository
- **Scope:** Initialize `spring-boot/.git`; add Java-specific ignore rules and record the Java repository's branch/commit convention.
- **Acceptance:** `spring-boot/` can be committed independently without staging the FastAPI root repository.
- **Checks:** `git -C spring-boot status`; verify only Java-project paths are visible.
- **Route/dependency evidence:** Required before every Java work-unit commit; depends only on the user-selected project boundary.
- **Delivery boundary:** One repository-bootstrap commit, or documented initialization if no files are needed.
- **Status:** Completed on `main` with local author configuration and commit `32725b111e29d392714626afc96a1cbf176cc1fd` (`chore: initialize Spring Boot repository`). `.gitignore` establishes Maven, IDE, and OS exclusions. The standalone repository can now be committed independently.

### SB1 — Establish build and strict-TDD foundation
- **Scope:** Maven Wrapper, Spring Boot application bootstrap, configuration, and the minimal non-business health boundary at `/actuator/health`.
- **Acceptance:** The standalone app starts on Java 21, the focused health test is GREEN, a packaged JAR responds locally, and no DATEV business route is introduced.
- **Checks:** Focused `HealthEndpointTest` RED before production code; `mvnw.cmd test`; `mvnw.cmd package`; launch JAR with `C:\ELO\java\bin\java.exe` and request `/actuator/health`.
- **Route/dependency evidence:** `spring-boot/src/test/java/com/elo/datevmock/HealthEndpointTest.java`; depends on SB0 for commits.
- **Delivery boundary:** One build-foundation commit including wrapper, build file, test, application bootstrap, and minimal run documentation.
- **Status:** **Complete.** The previously reported Maven Central "Permission denied" did not reproduce in a fresh shell: `mvn test` resolved the Spring Boot 3.3.5 parent and all starters cleanly against the default `~/.m2` repository (that earlier failure is presumed to have been a transient/local environment issue, not a real network restriction). RED was observed first: `HealthEndpointTest` failed with `IllegalStateException: Unable to find a @SpringBootConfiguration` because no application class existed yet. GREEN was reached by adding the minimal `com.elo.datevmock.DatevMockApplication` (`@SpringBootApplication`) — `mvn test`: `Tests run: 1, Failures: 0, Errors: 0`. `mvn package` produced `target/datev-mock-0.1.0-SNAPSHOT.jar`; launched with `C:\ELO\java\bin\java.exe -jar ... --server.port=58553` and `GET /actuator/health` returned `{"status":"UP"}`. No DATEV business route was introduced. Committed on `feat/sb1-build-foundation` as `60bbfb2` (`feat(sb1): add SpringBootApplication bootstrap to unblock health test`) in the standalone `spring-boot/.git` repository. `.gitignore` was extended with `.m2/` to keep an optional project-local Maven repository out of version control.
- **Route/delegation evidence:** Delegated direct. SB1 requires coordinated test, build, application, configuration, and documentation work across multiple files; strict TDD requires observed RED -> GREEN -> REFACTOR.

### SB2 — Shared DATEV contracts, XML, and format negotiation
- **Scope:** Model contracts, error/status conventions, DataContractSerializer-style XML roots/namespaces/order/`xsi:nil`, JSON projections, and FastAPI-equivalent `Accept`/format selection.
- **Acceptance:** Shared serializers render parity fixtures exactly for XML and JSON, including null, collection, ordering, and legacy cost-rate cases.
- **Checks:** Golden/black-box serializer tests and explicit content-negotiation tests.
- **Route/dependency evidence:** `app/xml_serializers.py`, models, and JSON/XML tests; prerequisite for every public API epic.
- **Delivery boundary:** One contract/serialization commit with fixtures and tests.
- **Status:** **Complete.** A generic, reflection-based XML rendering engine (`com.elo.datevmock.xml.DatevXmlRenderer`) ports `app/xml_serializers.py`'s DataContractSerializer conventions over Java `record` types: `i:nil="true"` for null, lowercase booleans, per-field namespace overrides (`genericNsAttrResolver`, porting `_generic_ns_attr`), and real recursion into nested records/lists via `RecordComponent` declaration order (avoiding the `toString()`-fallthrough bug class fixed in the Python renderer this session). A companion JSON projection (`DatevJsonMapper`, Jackson with `SNAKE_CASE` naming + `NON_NULL` inclusion) ports `_to_json`/`_strip_none` exactly (snake_case keys, null fields entirely absent). `FormatNegotiator` ports `_negotiate_format` (explicit unambiguous `Accept` wins; missing/wildcard/ambiguous falls back to the caller's default). Representative models: `CostCenter`+`CostRate` (with `withoutCostRates()` porting the `datev_api_version` legacy-mode gate — confirmed JSON-only, since `cost_rates` is absent from `CostCenter.XML_FIELD_ORDER` exactly as in the Python source) and `Creditor` with a nested list-of-objects field (`addresses` → `Address` → `AddressUsageType`) plus plain and common-namespace nil fields. Strict TDD: every class was RED (real compiler/missing-symbol failure observed) before GREEN. `mvn test`: `Tests run: 27, Failures: 0, Errors: 0` (26 new + the existing SB1 health test). No HTTP endpoints were added — SB2 is the shared engine other epics (SB5+) will mount controllers against; content-negotiation coverage is unit-level against `FormatNegotiator` directly. Committed on `feat/sb1-build-foundation` as `c69666d` (`feat(sb2): shared DATEV contracts, XML rendering, and format negotiation`) in the standalone `spring-boot/.git` repository (no remote configured there, so this commit is local-only, consistent with SB0/SB1).

### SB3 — Deterministic mock generation and read-state composition
- **Scope:** Fiscal-year-scoped deterministic fake datasets, stable identifiers, configuration-driven mode/version behavior, read assembly, and in-memory overrides without persistence leakage.
- **Acceptance:** Repeated reads for the same client/fiscal-year scope are stable; distinct scopes remain coherent; override precedence matches FastAPI.
- **Checks:** Deterministic-scope tests, configuration tests, and read-state/override integration tests.
- **Route/dependency evidence:** `app/data_store.py`, `app/scoped_data.py`, `app/config.py`, `app/overrides.py`, `tests/test_data_store.py`, `tests/test_config.py`.
- **Delivery boundary:** One mock-domain/state commit.
- **Status:** **Complete.** Ported `app/scoped_data.py`'s SHA256-seeded (`ScopeSeed`, `com.elo.datevmock.scoped`), scope-cached (`ConcurrentHashMap` + `computeIfAbsent`, so same scope key always returns the same cached list instance) deterministic generation for fiscal years, cost systems, cost centers, terms of payment, and creditors, via `ScopedDataService`. Referential-integrity cross-references are real: a fiscal year's `creditorTermOfPaymentId`/`debitorTermOfPaymentId` are backfilled from that same fiscal year's own generated terms-of-payment scope; a creditor's `addresseeId` is drawn from a global id pool (`GlobalAddresseePool` — a documented placeholder standing in for SB5's not-yet-ported real `Addressee` list, since master data is out of SB3's scope). Generated field *values* are not byte-identical to Python (different PRNGs, not a stated goal — see the class javadoc); the scoping *architecture* (stability, independence, real cross-references) is what's tested and proven, with a dedicated `ScopeSeedTest` proving true seed divergence deterministically (collision-free via SHA256) rather than asserting inequality of a downstream random field, which would carry a real if small chance of an unlucky coincidental match. Also ported the storage layer of `app/overrides.py` (`OverrideStore`/`OverrideEntry`, `com.elo.datevmock.overrides`): set/get-active/list/enable/disable/delete/clear, plus the pending-upload store/resolve flow for ambiguous fingerprint matches. Deliberately did **not** port `detect_candidates`/`detect_content_type`/`sanitize_xml` (upload-time XML-root/JSON-fingerprint detection across every DATEV resource type) or any router/multipart wiring — SB9's own scope explicitly names "multipart `file` override upload/resolve/list/update/delete", so that layer sits on top of this store later rather than being duplicated now. `app/config.py`'s `Settings`/`app/db.py`'s `merge_with_stored` were confirmed **not** needed by SB3: `datev_api_version` was already fully ported in SB2 (`MockSettings`) and isn't consulted by generation itself, only by the read-side legacy/modern gate; SQLite-backed write-overlay composition (`merge_with_stored`) is SB4's explicit scope ("SQLite overlays, validation, and reset semantics"), not SB3's — attempting it here would have duplicated that epic. `mvn test`: `Tests run: 50, Failures: 0, Errors: 0` (39 prior + 11 new override-store tests; the 9 scoped-data + 3 scope-seed tests already counted in that 39 from an earlier `test-compile`-confirmed RED). Committed on `feat/sb1-build-foundation` as `94d8664` (`feat(sb3): deterministic scoped mock generation and in-memory overrides`) in `spring-boot/.git`.

### SB4 — SQLite overlays, validation, and reset semantics
- **Scope:** Generic SQLite persisted records, create/update validation, conflict/not-found/status behavior, restart persistence, and reset behavior separating stored data from generated data, overrides, and logs.
- **Acceptance:** Write overlays survive restart where FastAPI does; invalid payloads and identifiers produce matching failures; reset restores the documented state.
- **Checks:** Persistence/restart tests, validation matrix, reset tests, and failure-status parity tests.
- **Route/dependency evidence:** `app/db.py`, write-endpoint tests, `tests/test_db.py`; shared dependency for master-data and accounting writes.
- **Delivery boundary:** One persistence/validation commit.
- **Status:** **Complete.** Ported `app/db.py`'s generic write-overlay module to Java: `com.elo.datevmock.store.StoredRecordStore` (SQLite via `org.xerial:sqlite-jdbc`, one `stored_records` table keyed on `(resource_type, record_id)`, a short-lived JDBC connection per call — same choice FastAPI made). Full CRUD parity: `upsertRecord`/`getRecord`/`listRecords`(+client/fiscal-year filters)/`deleteRecord`/`deleteRecords`(bulk)/`reset`/`listAllWithMeta`, plus the `created_at`-preserved/`updated_at`-changed upsert contract — every case in `tests/test_db.py` has a matching JUnit test (`StoredRecordStoreTest`, 12 tests), plus one FastAPI doesn't have: `writtenRecordSurvivesASimulatedRestart` opens a second `StoredRecordStore` instance against the same file to prove restart persistence for real. `RecordMapper` ports `record_to_dataclass`/`merge_with_stored` via reflection over Java record components (type-appropriate defaults for missing fields, `nilFields`, a `fieldMap` for source-key translation, stored-wins-on-shared-id union) — `RecordMapperTest`, 6 tests, exercised against the real `CostCenter` model from SB2. `ReferenceValidation`/`ValidationException` port `_validate_reference`'s 422-on-unknown-reference contract (`ReferenceValidationTest`, 3 tests) for SB5-SB7 controllers to call once they exist. `mvn test`: `Tests run: 71, Failures: 0, Errors: 0` (50 pre-existing + 21 new). Real RED observed before each class (compiler "Symbol nicht gefunden"). Reset semantics note: FastAPI's actual `/admin/api/reset` endpoint (`app/routers/admin.py::reset_data`) only resets the legacy `app/data_store.py` in-memory demo dataset, NOT `app/db.py`'s SQLite store, `app/scoped_data.py`'s caches, or `app/overrides.py` — there is no unified reset endpoint to port today. `StoredRecordStore.reset()` (matching `db.py::reset()`) is the correct SB4-scope unit; wiring a unified admin reset action across all four subsystems, if wanted, belongs to SB9 (admin API) alongside the rest of that endpoint surface. Not in scope here: no HTTP controllers (still SB5-SB7) and no wired-up conflict/not-found status codes beyond the 422 reference-validation contract, since FastAPI's own write endpoints don't raise 404/409 either (upsert-over-fake semantics, confirmed by reading `app/routers/accounting.py`). Commit: `cfeac1c` (`feat(sb4): SQLite write-overlay store, record mapping, and reference validation`).

### SB5 — Master-data API parity
- **Scope:** Client, addressee, bank, and employee reads/writes under `/datev/api/master-data/v1/*`.
- **Acceptance:** List/detail/create/update behavior, identifiers, field shapes, XML/JSON output, and failures match FastAPI.
- **Checks:** Ported parity tests from `test_master_data*.py` and relevant write-endpoint cases.
- **Route/dependency evidence:** `app/routers/master_data.py`: clients, addressees, banks, employees; depends on SB2–SB4.
- **Delivery boundary:** One master-data behavior commit.
- **Status:** Planned.

### SB6 — Accounting read API parity
- **Scope:** Client/fiscal-year reads and all accounting list/read-only projections: cost systems/centers, creditors/debitors, general-ledger accounts, payables/receivables, terms, sequences/keys, assets, proposal rules, and related fiscal-year resources.
- **Acceptance:** Every FastAPI accounting GET has an equivalent path, status, deterministic scope, fields, and XML/JSON behavior.
- **Checks:** Ported suites for fiscal structure, JSON, partners, payables/receivables, and miscellaneous accounting reads.
- **Route/dependency evidence:** `app/routers/accounting.py` GET decorators and endpoint constants, including `/datev/api/accounting/v1/clients/{client_id}/fiscal-years/*`; depends on SB2–SB4.
- **Delivery boundary:** One accounting-read commit, split only at coherent API-family boundaries.
- **Status:** Planned.

### SB7 — Accounting write API parity
- **Scope:** Accounting POST/PUT endpoints for partners, terms, cost/asset/sequences, and posting-proposal batches, using SB4 overlays and validation.
- **Acceptance:** Every FastAPI accounting mutation preserves success code, validation, immutable/generated-data rules, persisted overlay behavior, and subsequent read visibility.
- **Checks:** Ported `test_write_endpoints.py` and `test_write_endpoints_group_b.py`, plus restart/read-after-write cases.
- **Route/dependency evidence:** `app/routers/accounting.py` POST/PUT decorators, notably creditors, debitors, terms of payment, cost data, assets, accounting sequences, and posting proposals; depends on SB6 and SB4.
- **Delivery boundary:** One or more coherent accounting-write commits; keep each independently testable.
- **Status:** Planned.

### SB8 — DMS and diagnostics parity
- **Scope:** `GET /datev/api/dms/v1/domains`, `GET /datev/api/dms/v1/documents`, and `GET /datev/api/diagnostics/v1/echo`, including override behavior.
- **Acceptance:** DMS trees/documents and the fresh diagnostics echo match FastAPI fields, media types, and override semantics.
- **Checks:** Ported `test_dms.py`, `test_diagnostics.py`, and override integration tests.
- **Route/dependency evidence:** `app/routers/dms.py`, `app/routers/diagnostics.py`; DMS is self-designed and must follow the locked test contract rather than infer an official schema.
- **Delivery boundary:** One DMS/diagnostics commit.
- **Status:** Planned; depends on SB2–SB3.

### SB9 — Admin frontend/API/settings/override/log/SSE compatibility
- **Scope:** Existing `/admin` frontend and `/admin/api/*`: settings; master-data/accounting management; reset; stored records; multipart `file` override upload/resolve/list/update/delete; request logs; and `/admin/api/logs/stream` SSE. Also add a frontend "API base URL" setting (scheme+host+port, e.g. `https://127.0.0.1:58452` or `https://127.0.0.1:58553`) that all frontend API calls route through instead of assuming same-origin, defaulting to same-origin; enable CORS on both FastAPI and Spring Boot backends for cross-origin calls from the admin frontend's own origin.
- **Acceptance:** The existing frontend works against Spring unchanged; admin data operations, settings, overrides, logging limits, and live SSE behavior match FastAPI. The base-URL setting also lets the same frontend page successfully call the real DATEV production/test API or another local DATEV-compatible mock (e.g. `C:\Mockup\serve-0.1-generate.jar`) without code changes, limited only by that target's own auth/TLS/CORS posture.
- **Checks:** Ported `test_admin_api.py`, admin-page JS syntax check, override API/integration tests, request-log tests, multipart/SSE API checks, base-URL-switch manual smoke test against both backends, and manual admin smoke test.
- **Route/dependency evidence:** `app/routers/admin.py`, `app/request_log.py`, `app/overrides.py`; depends on SB3–SB8.
- **Delivery boundary:** One admin compatibility commit, or coherent UI/API slices with their matching tests.
- **Status:** Planned.

### SB10 — Contract-parity and regression verification
- **Scope:** Cross-route black-box comparison of the Java app against FastAPI/test fixtures, including success/failure statuses, XML/JSON, persistence restart, overrides, admin, and SSE.
- **Acceptance:** All observed FastAPI routes are accounted for; intentional differences are explicitly documented and approved rather than silently introduced.
- **Checks:** Full Maven suite, route inventory matrix, representative FastAPI-vs-Java comparisons, and regression report.
- **Route/dependency evidence:** All `app/routers/*.py`, `tests/`, and `examples/DATEV_Mock_Server_Reference.md`; depends on SB5–SB9.
- **Delivery boundary:** One verification/report commit.
- **Status:** Planned.

### SB11 — Packaging and local runbook
- **Scope:** Repeatable standalone JAR build/run instructions, configuration/port guidance, Java 21 prerequisite, and local smoke-test procedure.
- **Acceptance:** A developer can build and run `spring-boot/` independently without changing the FastAPI root application.
- **Checks:** Clean package, JAR launch, local health request, and documented startup smoke test.
- **Route/dependency evidence:** SB1 launcher and SB10 parity result; depends on SB10.
- **Delivery boundary:** One packaging/runbook commit.
- **Status:** Planned.

## Current evidence and blockers

- Java 21 is verified at `C:\ELO\java\bin\java.exe`: Azul OpenJDK 21.0.1, with `javac.exe` and `jar.exe`. Maven 3.9.16 is verified at `C:\apache-maven-3.9.16\\bin\\mvn.cmd` when `JAVA_HOME=C:\\ELO\\java`; it is not on the system `PATH`.
- Maven Central is reachable and dependency resolution works against the default `~/.m2` repository; the earlier "Permission denied" report did not reproduce and is presumed to have been a transient/local environment issue in that session, not a real network restriction. No blocker remains for further epics.
- `spring-boot/` was merged from its own standalone repository into this one via `git subtree add --prefix=spring-boot spring-boot-origin feat/sb1-build-foundation`, commit `82f6cb8` on `main`. SB0-SB3 (`32725b1`, `60bbfb2`, `c69666d`, `94d8664`) are verified real ancestors of `main`. The temporary `spring-boot-origin` remote was removed after the merge. A pre-merge backup of the standalone working tree remains at `C:\Users\eloadmin\spring-boot-standalone-backup` (outside this repo) until the user confirms it can be deleted.
- `mvn test`: `Tests run: 71, Failures: 0, Errors: 0` after SB4 (`sqlite-jdbc` 3.46.1.3 added to `pom.xml`; `datev_mock.db*` gitignored under `spring-boot/`, mirroring the FastAPI root `.gitignore`).

## Next action

**Implement SB5 (master-data API parity) with strict TDD, using `app/routers/master_data.py` and its tests in the FastAPI project as the authoritative contract.**
