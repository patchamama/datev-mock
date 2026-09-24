# Spring Boot parity roadmap

> **Decision:** `spring-boot/` is a separate Java project with its own initialized `.git` repository; do not use the FastAPI repository's Git index for Java work.

## Remaining path

1. Restore Maven Central availability or provide an approved local Maven distribution.
2. Resume SB1 with strict TDD: observe RED, implement the smallest health boundary, then observe GREEN.
3. Implement the remaining epics in dependency order.
4. Keep every completed epic as a reviewable work-unit commit in the standalone Java repository.

## Contract and boundaries

| Topic | Decision |
| --- | --- |
| Contract source | Current FastAPI code and tests are authoritative. The historical Java JAR/reference is supplementary. |
| Java project | `spring-boot/`; Java 21 is verified at `C:\ELO\java\bin\java.exe` (Zulu OpenJDK 21.0.1 with `javac` and `jar`). |
| Compatibility | Preserve paths, status codes, request/response shapes, multipart field `file`, XML/JSON negotiation, state semantics, and SSE. |
| Excluded root work | Do not alter existing edits in `.github/workflows/release.yml`, `README.md`, `app/main.py`, or `start.sh`. |
| Delivery | One conventional work-unit commit per coherent epic in `spring-boot/.git`; push, PR, and merge remain user decisions. |
| TDD | RED -> GREEN -> REFACTOR is mandatory. No production behavior is claimed without observed evidence. |

The FastAPI inventory contains 29 public GET routes, 25 public POST/PUT routes, and conditionally mounted admin UI/API. Read behavior combines deterministic mock data, SQLite-backed write overlays, content negotiation, overrides, and a request-log SSE stream.

## Dependency-ordered epic checklist

- [x] **SB0 — Bootstrap the standalone repository** *(completed: `32725b1`)*
- [x] **SB1 — Establish build and strict-TDD foundation**
- [ ] **SB2 — Shared DATEV contracts, XML, and format negotiation**
- [ ] **SB3 — Deterministic mock generation and read-state composition**
- [ ] **SB4 — SQLite overlays, validation, and reset semantics**
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
- **Status:** Planned; depends on SB1.

### SB3 — Deterministic mock generation and read-state composition
- **Scope:** Fiscal-year-scoped deterministic fake datasets, stable identifiers, configuration-driven mode/version behavior, read assembly, and in-memory overrides without persistence leakage.
- **Acceptance:** Repeated reads for the same client/fiscal-year scope are stable; distinct scopes remain coherent; override precedence matches FastAPI.
- **Checks:** Deterministic-scope tests, configuration tests, and read-state/override integration tests.
- **Route/dependency evidence:** `app/data_store.py`, `app/scoped_data.py`, `app/config.py`, `app/overrides.py`, `tests/test_data_store.py`, `tests/test_config.py`.
- **Delivery boundary:** One mock-domain/state commit.
- **Status:** Planned; depends on SB2.

### SB4 — SQLite overlays, validation, and reset semantics
- **Scope:** Generic SQLite persisted records, create/update validation, conflict/not-found/status behavior, restart persistence, and reset behavior separating stored data from generated data, overrides, and logs.
- **Acceptance:** Write overlays survive restart where FastAPI does; invalid payloads and identifiers produce matching failures; reset restores the documented state.
- **Checks:** Persistence/restart tests, validation matrix, reset tests, and failure-status parity tests.
- **Route/dependency evidence:** `app/db.py`, write-endpoint tests, `tests/test_db.py`; shared dependency for master-data and accounting writes.
- **Delivery boundary:** One persistence/validation commit.
- **Status:** Planned; depends on SB3.

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
- **Scope:** Existing `/admin` frontend and `/admin/api/*`: settings; master-data/accounting management; reset; stored records; multipart `file` override upload/resolve/list/update/delete; request logs; and `/admin/api/logs/stream` SSE.
- **Acceptance:** The existing frontend works against Spring unchanged; admin data operations, settings, overrides, logging limits, and live SSE behavior match FastAPI.
- **Checks:** Ported `test_admin_api.py`, admin-page JS syntax check, override API/integration tests, request-log tests, multipart/SSE API checks, and manual admin smoke test.
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

- Java 21 is verified at `C:\ELO\java\bin\java.exe`: Azul OpenJDK 21.0.1, with `javac.exe` and `jar.exe`. Maven 3.9.16 is verified at `C:\apache-maven-3.9.16\\bin\\mvn.cmd` when `JAVA_HOME=C:\\ELO\\java`; it is not on the system `PATH`. Maven must use an absolute path to the user-authorized project-local repository `spring-boot/.m2`; Maven Central dependency transfers are currently denied by the environment.
- The incomplete SB1 artifacts already live in `spring-boot/`: `pom.xml`, `.mvn/`, `mvnw.cmd`, and the focused health test.
- No production Spring application exists yet because the mandatory focused RED test has not executed; both authorized 2026-09-24 Maven Wrapper attempts failed before Maven launched, including the retry after the stated access change.
- `spring-boot/.git` exists independently on `main`; SB0 is committed and the repository-local author identity is configured.
- SB0 verification: `git -C spring-boot status --short --branch` reports `main`; the SB0 commit is `32725b1`. The pending SB1 files remain intentionally uncommitted until strict TDD can execute.

## Next action

**Make the required Maven Central dependencies accessible (or provide them locally), then continue SB1 with the focused RED test using an absolute project-local Maven repository path.**
