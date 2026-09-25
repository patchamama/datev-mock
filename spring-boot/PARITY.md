# SB10 — FastAPI vs. Spring Boot route parity matrix

Generated for epic **SB10 — Contract-parity and regression verification**
(`odd/tasks/datev-mock-spring-boot-migration.md`). Method: full-text read of
every FastAPI router (`app/routers/*.py`, `app/main.py`) and every Spring
controller (`spring-boot/src/main/java/com/elo/datevmock/web/*.java`), grep
-verified for `@*Mapping` annotations across the whole Java tree to rule out
missed controllers. No live black-box HTTP comparison was run (out of scope
for this pass, per SB10 instructions) — this is a static route/behavior
inventory cross-reference plus both automated test suites as evidence.

## Totals

| Stack | Routes |
| --- | --- |
| FastAPI (`app/routers/*.py`) | 75 (1 diagnostics + 13 master-data + 39 accounting [20 GET + 19 write] + 2 DMS + 20 admin [19 JSON API + 1 HTML page]) |
| Spring Boot (`com.elo.datevmock.web.*`) | 63 (1 diagnostics + 13 master-data + 28 accounting [16 GET + 12 write] + 2 DMS + 19 admin JSON API) |
| Difference | 12 — **fully accounted for by pre-existing, already-documented gaps** (see below). Zero new undocumented gaps. Zero Java-only routes with no FastAPI counterpart. |

## Diagnostics — 1:1, exact match

| Method | Path | FastAPI | Java |
| --- | --- | --- | --- |
| GET | `/datev/api/diagnostics/v1/echo` | `get_echo` | `getEcho` |

## Master data — 13:13, exact match

| Method | Path | FastAPI | Java |
| --- | --- | --- | --- |
| GET | `/datev/api/master-data/v1/clients` | ✓ | ✓ |
| POST | `/datev/api/master-data/v1/clients` | ✓ | ✓ |
| PUT | `/datev/api/master-data/v1/clients/{id}` | ✓ | ✓ |
| PUT | `/datev/api/master-data/v1/clients/{id}/responsibilities` | ✓ | ✓ |
| GET | `/datev/api/master-data/v1/addressees` | ✓ | ✓ |
| GET | `/datev/api/master-data/v1/addressees/{id}` | ✓ | ✓ |
| POST | `/datev/api/master-data/v1/addressees` | ✓ | ✓ |
| PUT | `/datev/api/master-data/v1/addressees/{id}` | ✓ | ✓ |
| GET | `/datev/api/master-data/v1/banks` | ✓ | ✓ |
| GET | `/datev/api/master-data/v1/employees` | ✓ | ✓ |
| GET | `/datev/api/master-data/v1/employees/{id}` | ✓ | ✓ |
| POST | `/datev/api/master-data/v1/employees` | ✓ | ✓ |
| PUT | `/datev/api/master-data/v1/employees/{id}` | ✓ | ✓ |

## DMS — 2:2, exact match

| Method | Path | FastAPI | Java |
| --- | --- | --- | --- |
| GET | `/datev/api/dms/v1/domains` | ✓ | ✓ |
| GET | `/datev/api/dms/v1/documents` | ✓ | ✓ |

## Admin JSON API — 19:19, exact match (plus 1 documented HTML-page difference)

| Method | Path | FastAPI | Java |
| --- | --- | --- | --- |
| GET | `/admin/api/settings` | ✓ | ✓ |
| PUT | `/admin/api/settings` | ✓ | ✓ |
| GET | `/admin/api/clients/master-data` | ✓ | ✓ |
| POST | `/admin/api/clients/master-data` | ✓ | ✓ |
| PUT | `/admin/api/clients/master-data/{id}` | ✓ | ✓ |
| DELETE | `/admin/api/clients/master-data/{id}` | ✓ | ✓ |
| GET | `/admin/api/clients/accounting` | ✓ | ✓ |
| POST | `/admin/api/clients/accounting` | ✓ | ✓ |
| PUT | `/admin/api/clients/accounting/{id}` | ✓ | ✓ |
| DELETE | `/admin/api/clients/accounting/{id}` | ✓ | ✓ |
| POST | `/admin/api/reset` | ✓ | ✓ |
| GET | `/admin/api/stored-records` | ✓ | ✓ |
| GET | `/admin/api/logs` | ✓ | ✓ |
| GET | `/admin/api/logs/stream` (SSE) | ✓ | ✓ |
| POST | `/admin/api/overrides` (multipart `file`) | ✓ | ✓ |
| POST | `/admin/api/overrides/resolve` | ✓ | ✓ |
| GET | `/admin/api/overrides` | ✓ | ✓ |
| PUT | `/admin/api/overrides/{key}` | ✓ | ✓ |
| DELETE | `/admin/api/overrides/{key}` | ✓ | ✓ |
| GET | `/admin` (HTML admin page) | ✓ | **absent — by design** |

`GET /admin` has no Java equivalent. This is the documented "same frontend for
both backends" architecture decision (`odd/tasks/...md`, "Contract and
boundaries" table, and SB9's own honest gap (5)): the shared `/admin` page is
served only by FastAPI; the Spring Boot backend is one of the page's
selectable API targets via its configurable base-URL setting, not a second
copy of the page itself.

## Accounting — 16:16 GET-matches / 4 GET missing, 12:12 write-matches / 7 write missing

All 16 implemented Java GET routes and all 12 implemented Java write routes
match a FastAPI route 1:1 by path (fiscal-year-scoped prefix
`/datev/api/accounting/v1/clients/{clientId}/fiscal-years/{fiscalYearId}/...`
in both). The 11 FastAPI routes with **no** Java equivalent are exactly the
set already named as a deliberate, documented gap in SB7's own "Honest gaps"
section — reproduced here for the parity record, not as a new finding:

| Method | Path | Status |
| --- | --- | --- |
| GET | `.../cost-systems/{id}/cost-center-properties` | not implemented (SB7 gap) |
| GET | `.../cost-systems/{id}/cost-sequences` | not implemented (SB7 gap) |
| GET | `.../cost-sequences/{id}/cost-accounting-records` | not implemented (SB7 gap) |
| GET | `.../fiscal-years/{id}/various-addresses` | not implemented (SB7 gap) |
| PUT | `.../cost-center-properties/{id}` | not implemented (SB7 gap) |
| PUT | `.../cost-sequences/{id}` | not implemented (SB7 gap) |
| POST | `.../cost-sequences/{id}/cost-accounting-records` | not implemented (SB7 gap) |
| POST | `.../fiscal-years/{id}/various-addresses` | not implemented (SB7 gap) |
| POST | `.../cost-systems/{id}/internal-cost-services` | not implemented (SB7 gap) |
| POST | `.../fiscal-years/{id}/accounting-sequences` (create-only, no GET) | not implemented (SB7 gap) |
| POST | `.../posting-proposals-cash-register/batch` | not implemented (SB7 gap) |

11 accounting gaps + 1 admin-page gap = 12 = the full 75 − 63 route-count
difference. **Every missing route is a route this project already knew about
and already decided to defer** — none of them are a new finding from this
epic.

## Test-suite evidence

- Java: `mvn -o test` (system Maven 3.9.16, `JAVA_HOME=C:\ELO\java`) —
  **`Tests run: 151, Failures: 0, Errors: 0`**, `BUILD SUCCESS`. Per-class
  breakdown from `target/surefire-reports/*.txt` sums to 151 across 21 test
  classes (largest: `AccountingControllerTest` 31, `AdminControllerTest` 16,
  `MasterDataControllerTest` 12, `StoredRecordStoreTest` 12). Identical count
  to what SB9 last reported — expected, since SB10 adds no production code
  or tests, only this verification pass.
- Python: `.venv\Scripts\python.exe -m pytest -q` from the repo root —
  **`375 passed`**, 2 unrelated deprecation warnings (`httpx`/`starlette`
  test-client warnings, not app behavior), 0 failures. Matches the README's
  own "375 passing" badge.

## Consolidated "Honest gaps" — carried forward, not new

These are restated here for SB10's own record, per this epic's instruction
to fold known gaps in rather than re-flag them. All were already documented
under their originating epic; none are new findings from this pass.

- **Route-level (SB7):** 11 accounting sub-resources not implemented — see
  table above.
- **Route-level (architecture decision / SB9):** no Java-served `/admin`
  HTML page; the shared frontend is FastAPI-served only, by the project's
  own "same frontend, configurable backend URL" decision.
- **SB5:** write bodies accepted as raw `Map<String,Object>`, not typed/
  validated DTOs (no Pydantic-equivalent required-field/type checks);
  `AddresseeWrite`'s ~10 passthrough fields not individually modeled; not
  every `test_master_data*.py` case was ported (representative coverage).
- **SB6/SB7:** `expand=all` query-param gate not implemented (creditors/
  debitors nested fields are unconditionally nilled — currently invisible
  since the generator never populates them, but real once a caller expects
  `expand=all` to surface posted nested data); `FiscalYear` stays
  field-trimmed (3 of ~20 real fields); generated field *values* are
  representative, not byte-identical to Python (different PRNGs, a stated
  non-goal since SB3); bulk PUT (array body) for creditors/debitors is
  implemented but not directly test-covered.
- **SB9:** `AdminDataStore` (admin-panel CRUD) does **not** share state with
  SB5's `MasterDataController`/SB6's `AccountingController` public read
  endpoints — each side keeps its own independent deterministic
  generator/state, mirroring FastAPI's own router-level independence. The
  task doc's own "Next action" text floated retrofitting this as part of
  SB10; **it was deliberately left alone in this pass** — SB10's brief here
  is verification and reporting, not production-code changes, so this
  remains an open item for a future epic or explicit user decision, not
  something silently fixed or left ambiguous. SSE test is a shape/smoke
  test, not a full backlog-then-live-then-keep-alive integration test
  (matches FastAPI's own stated test depth). Admin JSON-casing for
  master-data/accounting-client responses is close but not byte-exact for
  the handful of FastAPI-only always-`null` synthetic fields, which are
  simply absent from the Java response. Not every `test_admin_api.py` case
  was ported (representative coverage). No interactive/browser smoke test
  of the actual `/admin` page was performed (Java has no page to load).
  `CorsConfig`'s 8 enumerated origin patterns are equivalent to, but not a
  literal port of, FastAPI's single regex — a new host/scheme combination
  needs a 9th pattern added by hand.
- **General:** no live black-box HTTP comparison between two running
  servers was performed this epic (explicitly out of scope for SB10 per its
  own instructions); parity confidence here rests on route inventory +
  both test suites + explicit documentation of every known difference.
