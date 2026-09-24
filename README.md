# DATEV Desktop API Mock

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pytest](https://img.shields.io/badge/tests-375%20passing-brightgreen?logo=pytest&logoColor=white)](tests/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Status](https://img.shields.io/badge/status-active-success)](#status)

A local FastAPI mock of DATEV's local Desktop API (the REST interface a DATEV
workstation normally exposes on `https://<local-ip>:58452/datev/api/...`),
built for developing and testing against DATEV integrations without a real
DATEV installation.

It reproduces the exact response shapes of the endpoints used during real
capture, and additionally supports the response format documented on DATEV's
official developer portal where the two disagree (see
[Key decisions](#key-decisions) below).

## Install and run (one line)

No prerequisites needed — not even Python. These installers download the
repository, bootstrap Python (system Python if found, otherwise a portable,
project-local download — no system-wide install, no admin/root rights),
install dependencies, generate the HTTPS cert, and start the server, all in
one command:

**Windows** (cmd.exe or PowerShell):

```
powershell -c "iwr -useb https://raw.githubusercontent.com/patchamama/datev-mock/main/scripts/install.bat -OutFile install.bat; .\install.bat"
```

**Linux**:

```
curl -fsSL https://raw.githubusercontent.com/patchamama/datev-mock/main/scripts/install.sh | bash
```

**macOS**:

```
curl -fsSL https://raw.githubusercontent.com/patchamama/datev-mock/main/scripts/install.sh | bash
```

Each command clones the repo into a `datev-mock/` folder in the current
directory (or updates it if already present) and immediately starts the
mock. Once it's running, open `https://127.0.0.1:58452/admin` (accept the
self-signed certificate warning once) or `https://127.0.0.1:58452/docs` for
Swagger.

Already have the repo cloned? See [Quick start](#quick-start) below.

## Contents

- [Install and run (one line)](#install-and-run-one-line)
- [Status](#status)
- [Quick start](#quick-start)
- [Endpoints mocked](#endpoints-mocked)
- [Key decisions](#key-decisions)
- [Custom overrides](#custom-overrides)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Running the tests](#running-the-tests)
- [Running the server](#running-the-server)
- [Technology](#technology)

## Status

**GREEN — implemented and passing.** All 375 tests pass
(`.venv\Scripts\python -m pytest tests/ -v`), and the server has been
verified live over real HTTPS (the 23 original read-only endpoints, the 26
new SQLite-backed write endpoints, the live request log, the Bootstrap admin
UI with its full endpoint catalog and custom-override uploads, and Swagger
UI). Eleven epics complete:
[`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (base API),
[`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md)
(settings/admin UI),
[`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md)
(20 additional endpoints: Master Data addressees/banks, 15 Accounting
sub-resources, DMS),
[`odd/tasks/datev-mock-admin-ui-polish.md`](odd/tasks/datev-mock-admin-ui-polish.md)
(Bootstrap admin UI + full endpoint catalog),
[`odd/tasks/datev-mock-custom-overrides.md`](odd/tasks/datev-mock-custom-overrides.md)
(upload a custom XML/JSON example to temporarily override any endpoint's
response),
[`odd/tasks/datev-mock-real-data-reconciliation.md`](odd/tasks/datev-mock-real-data-reconciliation.md)
(reconciled every endpoint's field set and response format against data
captured from a real DATEV installation — see [Content
negotiation](#content-negotiation-xml-and-json) below for what changed),
[`odd/tasks/datev-mock-write-endpoints-and-observability.md`](odd/tasks/datev-mock-write-endpoints-and-observability.md)
(26 new SQLite-backed `POST`/`PUT` write endpoints across 14 DATEV resource
families — 7 already GET-modeled, 7 brand new, the latter also adding 6 new
GET endpoints — plus a live browser/CLI request log with
unregistered-route and wrong-method detection; see [Write endpoints and
persistence](#write-endpoints-and-persistence) below for the resulting,
now only partial, in-memory-by-default philosophy),
[`odd/tasks/datev-mock-exe-release.md`](odd/tasks/datev-mock-exe-release.md)
(one-line installers for Windows/Linux/macOS, a standalone `datev-mock.exe`
built and published via a tag-triggered GitHub Actions release workflow),
[`odd/tasks/datev-mock-referential-integrity.md`](odd/tasks/datev-mock-referential-integrity.md)
(deterministic per-scope fake-data generation so `client_id`/
`fiscal_year_id`/`cost_system_id` actually filter GET responses instead of
being ignored, real cross-references between resources instead of
unrelated/coincidental ids, and 422 write-side validation for every
FK-shaped write field — see [Referential integrity and path-param
scoping](#referential-integrity-and-path-param-scoping) below), and
[`odd/tasks/datev-mock-static-demo-gh-pages.md`](odd/tasks/datev-mock-static-demo-gh-pages.md)
(a static, read-only snapshot of a fixed demo id set published to GitHub
Pages — see [Static demo on GitHub
Pages](#static-demo-on-github-pages) below), and
[`odd/tasks/datev-mock-expand-nested-content.md`](odd/tasks/datev-mock-expand-nested-content.md)
(real `expand=all` nested content for creditors/debitors, spec-grounded
per a fresh official-spec extraction, plus an RFC3339 timestamp fix found
via live debugging of a real integration client — see [Expand and nested
content](#expand-and-nested-content) below).
See each task doc for full breakdowns, decisions, and progress logs.

## Quick start

Already have the repo cloned locally? No Python installed? These scripts
bootstrap a project-local Python (system Python if available, otherwise a
portable download into this folder — no system-wide install, no admin
rights), install dependencies, generate the HTTPS cert, and start the
server:

- Windows: `start.bat`
- Linux/macOS: `./start.sh`

Then open `https://127.0.0.1:58452/admin` (accept the self-signed cert
warning once) or `https://127.0.0.1:58452/docs` for Swagger.

Integration client fighting the self-signed cert's trust chain (common
with Java HTTP clients)? Set `DATEV_MOCK_HTTP=1` before starting to skip
TLS entirely and serve plain HTTP on the same port instead — e.g.
`DATEV_MOCK_HTTP=1 ./start.sh` (Linux/macOS) or `set DATEV_MOCK_HTTP=1 && start.bat`
(Windows). Off by default: HTTPS matches the real DATEV Desktop API, and a
self-signed cert doesn't exercise anything representative of production
DATEV's own (publicly-trusted) cert anyway, so this costs no real fidelity.

Windows only, no Python at all, don't want the source checkout? Grab the
standalone `datev-mock.exe` from the [Releases
page](https://github.com/patchamama/datev-mock/releases) and run it — it
carries its own Python runtime (built with PyInstaller) and creates
`settings.json`/`datev_mock.db`/`certs/` next to itself on first run.

## Endpoints mocked

**Base API** (real-capture XML, base project — see
[Key decisions](#key-decisions)):

| Method | Path | Format |
|---|---|---|
| `GET` | `/datev/api/diagnostics/v1/echo` | XML |
| `GET` | `/datev/api/master-data/v1/clients` | XML (default) **or** JSON (`Accept: application/json`) |
| `GET` | `/datev/api/accounting/v1/clients` | XML (default) **or** JSON (`Accept: application/json`) |

All three match the real .NET `DataContractSerializer` XML conventions
(root element names, namespaces, `i:nil="true"` for null fields) observed in
real captured traffic used locally for shape reference only. That capture
contains sensitive real-environment data and is **not** included in this
repository (kept local-only, git-ignored) — no real values from it are
reused anywhere in the mock's data, only field shapes.

**Extended endpoints** (see [Extended endpoint
sourcing](#extended-endpoint-sourcing) and [Content
negotiation](#content-negotiation-xml-and-json) below for how each area's
format was decided):

| Area | Format | Endpoints |
|---|---|---|
| Master Data | JSON-only | `GET /master-data/v1/addressees`, `GET /master-data/v1/addressees/{addressee-id}` (real 404-on-unknown-id lookup), `GET /master-data/v1/banks` |
| Accounting | XML (default) **or** JSON, all 15 | `GET /accounting/v1/clients/{client-id}/fiscal-years`, and under `.../fiscal-years/{fiscal-year-id}/`: `cost-systems` (+`cost-systems/{id}/cost-centers`), `creditors`, `debitors`, `general-ledger-accounts`, `accounts-payable` (+`/condense`), `accounts-receivable/condense`, `accounting-sequences-processed`, `accounting-transaction-keys`, `assets/stocktakings`, `posting-proposal-rules-incoming-invoices`, `posting-proposal-rules-outgoing-invoices`, `terms-of-payment` |
| DMS | JSON-only | `GET /dms/v1/domains`, `GET /dms/v1/documents` — **self-designed schema**, no official spec exists for this area at all (see caveat below) |

None of the extended endpoints filter by their path parameters (`client-id`/
`fiscal-year-id`/`cost-system-id` are accepted but ignored — every call
returns the same fake dataset) except the one noted 404 lookup, which
mirrors observed real behavior. Query params (`select`/`filter`/`skip`/
`top`/`expand`) are documented by DATEV but not implemented anywhere in this
mock — out of scope until an actual consumer needs them.

**Write endpoints** (new, SQLite-backed — see [Write endpoints and
persistence](#write-endpoints-and-persistence) below): 26 `POST`/`PUT`
operations across 14 resource families, on top of the 23 read-only
endpoints above — 15 operations across the 7 Group A families already
listed above (debitors, creditors, terms-of-payment, asset stocktakings,
cost-centers, master-data clients, addressees — each gets a matching
`GET` round-trip), and 11 operations across 7 brand-new Group B families
(`cost-center-properties`, `cost-sequences` + `cost-accounting-records`,
`various-addresses`, `employees`, `internal-cost-services`,
`accounting-sequences`, and the three `posting-proposals-*/batch`
endpoints) — the latter also add 6 new `GET` endpoints (Group B resources
that have a documented list/detail view; 5 of the 7 are create-only per
DATEV's own spec, no `GET` invented where none exists). Full per-resource
route list and request-body field tables:
[`odd/tasks/datev-mock-write-endpoints-and-observability.md`](odd/tasks/datev-mock-write-endpoints-and-observability.md).

## Key decisions

### Content negotiation (XML and JSON)

The very first version of this mock treated XML/JSON `Accept`-header
negotiation as a quirk specific to `accounting/v1/clients` (see [Origin of
this decision](#origin-of-this-decision) below). Real DATEV traffic
captured later — from the user's own live installation, shape-only, never
committed (see [`examples/`](examples/)) — showed the same pattern applies
far more broadly: `debitors` came back as XML while `creditors` (same
system, same session) came back as JSON, and `master-data/clients` turned
out to have a JSON projection too, alongside its known XML shape.

**Current decision: every one of the 15 Accounting sub-resources, plus
`accounting/v1/clients` and `master-data/v1/clients`, supports both XML
(default) and JSON (`Accept: application/json`)** via the same
`Accept`-header mechanism, on the same port, no second binding. Master Data
`addressees`/`banks` and DMS remain JSON-only — no evidence of an XML shape
exists for those.

Evidence quality varies per endpoint and is documented explicitly in code
and tests rather than overstated:
- **Confirmed by direct real capture**: `accounting/v1/clients`,
  `cost-systems`, `debitors` (and `creditors`, by the same contract
  family), `master-data/clients`'s JSON projection.
- **Inferred by a consistent pattern** (`ArrayOf<Name>` root,
  `http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.<Name>`
  namespace — the convention every confirmed sample follows): the
  remaining sub-resources, where either no real XML capture exists at all,
  or the real capture turned out to be JSON content despite an `.xml`
  filename.

A handful of earlier assumptions turned out to be wrong once real data
arrived, and were corrected rather than preserved: `accounting/v1/clients`
JSON's `number` is a real integer (not the string the official docs'
example showed), `general-ledger-account.main_function`/
`main_function_number`'s valid-value sets needed `0` added,
`accounts-receivable-condense`'s invented `dunning_level` field doesn't
exist (the real field is `has_dunning_block`), and creditors/debitors don't
populate nested `natural_person`/`legal_person` sub-objects by default.

Full write-up, per-endpoint evidence, and the full correction log:
[`odd/tasks/datev-mock-real-data-reconciliation.md`](odd/tasks/datev-mock-real-data-reconciliation.md).

#### Origin of this decision

The very first version of this project found two sources disagreeing on
`accounting/v1/clients` specifically:

- **Real captured traffic** (local-only, not in this repo): XML, port 58452,
  HTTPS.
- **Official DATEV developer docs** (developer.datev.de, Accounting product
  v1.7.4): JSON, port 58454, plain HTTP — confirmed example:
  ```json
  [{"company_data":{"creditor_identifier":"DE98ZZZ09999999999"},"id":"78a11a29-2a32-4a5e-a73b-632f6aeae131","name":"DATEVconnect GmbH","number":"47011"}]
  ```

That led to the original `Accept`-header negotiation mechanism, later
generalized to all 15 sub-resources as described above. Documented
OData-style query params (`select`, `filter`, `skip`, `top`, `expand`) are
explicitly out of scope for now.

Full write-up: [`odd/tasks/datev-mock.md` → "Decisions"](odd/tasks/datev-mock.md#decisions).

### Extended endpoint sourcing

The 20 extended endpoints (everything beyond the original 3) were scoped
from a gap analysis against a separate, existing internal DATEV mock tool.
Two different evidence qualities apply:

- **Master Data (addressees, banks) and all 15 Accounting sub-resources**:
  built from DATEV's actual official OpenAPI 3.0.1 specs (Accounting
  v1.5.0, Client Master Data v1.6.0), extracted from that internal tool and
  used as the schema source of truth — exact field names, types, and enum
  values, not guesswork. A few real quirks are preserved faithfully rather
  than "fixed": `general-ledger-account.main_function`/`main_function_number`
  use hardcoded valid-value lookup sets (the spec types them as plain
  integers with no `enum`, real constraints are description-text only),
  `cost-center.cost_rates[].valid_from`/`valid_to` are integer-encoded
  `YYYYMMDD` dates (not ISO date-time strings like everywhere else), and
  `accounts-payable`/`accounts-payable/condense` intentionally share one
  schema (condense is a server-side aggregation, not a different shape).
  The 15 Accounting sub-resources' field sets and formats were later
  reconciled against real captured DATEV data — see [Content
  negotiation](#content-negotiation-xml-and-json) above.
- **DMS (domains, documents)**: **no official spec exists** for this area
  at all (confirmed by exhaustive search) — the schema is self-designed
  from two one-line descriptions in an internal reference doc ("domain/
  folder/register tree" and "document metadata including amount, class,
  GUIDs, and timestamps"). Lower fidelity than everything else in this
  mock, by necessity, not oversight — treat DMS responses as illustrative
  shape only, not a verified DATEV contract. Real evidence confirms the
  DMS plugin is absent/not loaded on the user's own real installation
  (both `dms/v1/domains` and `dms/v1/documents` return a "PlugIn not
  loaded" error there) — this mock's DMS implementation has no real
  counterpart to validate against at all, by DATEV installation
  configuration, not a mock deficiency.

Full write-up: [`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md).

### Write endpoints and persistence

This mock started **read-only by design** — see [Editable
datasets](#settings--admin-ui) and [Custom
overrides](#custom-overrides) below, both still true, unchanged, for the
things they cover. This epic added genuine `POST`/`PUT` write endpoints on
top of that, which changes the persistence story for the resources they
touch:

- **Where the write operations came from**: the same two official DATEV
  OpenAPI 3.0.1 specs already used as ground truth for the 20 extended
  read endpoints above (Accounting v1.5.0, Client Master Data v1.6.0),
  cross-referenced against which paths also document a `GET` — i.e. which
  ones can round-trip (write, then read back). **Group A** is the 7
  resource families this mock already modeled for reading (debitors,
  creditors, terms-of-payment, asset stocktakings, cost-centers,
  master-data clients, addressees) — writing one now makes it appear in
  that same resource's existing `GET`, JSON or XML. **Group B** is 7
  brand-new resource families with no prior `GET` model at all
  (`cost-center-properties`, `cost-sequences` + `cost-accounting-records`,
  `various-addresses`, `employees`, `internal-cost-services`,
  `accounting-sequences`, and the three `posting-proposals-*/batch`
  endpoints) — a matching `GET` route was added wherever the spec
  documents one; the 5 operations the spec itself defines as create-only
  (no `GET` in the spec) stay `POST`-only rather than inventing a read
  endpoint the real API doesn't have. Full per-operation field tables:
  [`odd/tasks/datev-mock-write-endpoints-and-observability.md` →
  "Appendix A"](odd/tasks/datev-mock-write-endpoints-and-observability.md#appendix-a--resolved-request-body-field-tables-spec-derived-structural-only).
- **SQLite, one generic table** (`app/db.py`, stdlib `sqlite3`, no new
  dependency): every one of the 26 write operations, across all 14
  resource families, is backed by a single `stored_records` table
  (`resource_type`, `record_id`, the record as `data_json`, timestamps)
  rather than 14 bespoke per-resource schemas. This matches how the rest
  of the mock already treats every `GET` response — a dataclass projected
  to JSON/XML — so a new resource family needs a new Pydantic model and
  router wiring, not a database migration. `datev_mock.db` is created on
  first write, at the project root, **git-ignored** (same precedent as
  `settings.json`).
- **This is a deliberate exception to the rest of the mock's "everything
  resets on restart" philosophy.** The 2 admin-editable datasets
  (master-data/accounting clients, under [Editable
  datasets](#settings--admin-ui)) and [custom
  overrides](#custom-overrides) remain in-memory only, unchanged — still
  gone on restart, by design, exactly as before. Records written through
  any of the 26 new `POST`/`PUT` endpoints are different: they persist in
  `datev_mock.db` and **do survive a restart** — verified live by writing
  a record, killing the server process, starting a fresh one against the
  same `datev_mock.db` file, and confirming the record was still there.
  That was the explicit point of choosing SQLite for this one part of the
  mock instead of extending the existing in-memory pattern — if you were
  relying on this mock's blanket "everything resets" behavior for a
  resource that now has a write endpoint, that no longer holds; every
  other resource in the mock is unaffected.
- **Live request/response log and unregistered-route detection**: a small
  ASGI middleware (`app/request_log.py`) captures every request into (a) a
  bounded in-memory ring buffer, (b) a line printed to the CLI/terminal on
  every request, and (c) a Server-Sent-Events stream for the browser. It
  shows up in the admin UI as the **Live Request Log** card (expandable
  rows for full request/response detail, color-coded by HTTP method and
  status-code range) and is also queryable directly at `GET
  /admin/api/logs` (snapshot) and `GET /admin/api/logs/stream` (SSE).
  Because the same middleware sees every request regardless of whether a
  route matched, it distinguishes three cases in each log entry:
  `unmatched: true` for a genuinely unregistered path (no route matches
  at all — a real gap in mock coverage, logged at `WARNING` on the CLI
  with an `[UNMATCHED]` marker and highlighted in the UI), versus
  `unmatched: false` both for a legitimate business-logic 404 (e.g. an
  addressee lookup by an unknown id — a real route, correct 404) and for
  a `405 Method Not Allowed` on a real but wrong-verb request (e.g. `GET`
  on one of the create-only `posting-proposals-*/batch` endpoints) — both
  of the latter are matched routes behaving correctly, not coverage gaps.
  Stored records written through the new write endpoints are visible in
  the admin UI's **Stored records** card and at `GET
  /admin/api/stored-records`.

### Referential integrity and path-param scoping

Every accounting GET route under `/clients/{client_id}/fiscal-years/
{fiscal_year_id}[/cost-systems/{cost_system_id}]/...` used to **ignore**
those path params entirely and return one single global fake dataset,
generated once at process startup — and cross-referenced fields
(`Creditor.addressee_id`, `OpenItem.term_of_payment_id`, etc.) either
pointed at brand-new unrelated UUIDs or matched another resource's ids only
by arithmetic coincidence. This epic replaced both:

- **Deterministic per-scope generation, not strict validation.** Any
  `client_id`/`fiscal_year_id`/`cost_system_id` a caller supplies
  deterministically generates (and caches, for the process lifetime) its
  own internally-consistent dataset the first time it's used — seeded via
  SHA256 of the scope key, not Python's salted `hash()`. Two calls with the
  same scope always return identical data; different scopes return
  different data. **No scope id is ever rejected as "unknown"** — a
  deliberate choice over 404-ing on unrecognized ids, so ad hoc integration
  testing with a caller's own arbitrary ids keeps working, while still
  guaranteeing real internal consistency per scope.
- **Real cross-references, not reinvented arithmetic.** `Creditor`/
  `Debitor.addressee_id` now draws from the actual global `Addressee.id`
  list; `OpenItem.term_of_payment_id`/`accounting_sequence_id`/
  `kost1_cost_center_id`, `AssetStocktaking.general_ledger_account`, and
  `PostingProposalRule`'s transaction-key/account-number links all draw
  from their own scope's actually-generated records — fetch a creditor,
  then `GET` its `addressee_id` from `/master-data/v1/addressees`, and it's
  really there.
- **Write-side FK validation.** Every write endpoint with an FK-shaped body
  field (`addressee_id`, `term_of_payment_id`, cost-center/general-ledger/
  accounting-transaction-key links, `employee_id` on client
  responsibilities, ...) now rejects an unresolvable reference with `422`,
  checked against the union of that scope's generated data and whatever's
  already been written via SQLite — exactly what a subsequent `GET` in the
  same scope would show. A handful of fields with no modeled target
  resource at all (`business_partner_relation_id`, the
  organization/establishment/functional-area id triads) stay deliberately
  unvalidated, each flagged with a code comment rather than silently
  ignored.
- Master data (`clients`/`addressees`/`banks`/`employees`) and DMS
  (`domains`/`documents`) were already correctly modeled and stay global/
  unscoped — this epic only touched the accounting sub-resources nested
  under a client/fiscal-year path.

### Static demo on GitHub Pages

GitHub Pages is static hosting only — no server compute, no arbitrary
port, so the real dynamic mock (writes, any client/fiscal-year id, the
live request log, the admin UI) can't run there; its whole purpose is
emulating a *local* DATEV Desktop API in the first place. What GitHub
Pages *can* honestly serve: a **static, read-only snapshot** of a small,
fixed demo id set.

- `scripts/generate_static_demo.py` snapshots every Group-A GET endpoint
  (the ones with real fake data — see [Extended endpoint
  sourcing](#extended-endpoint-sourcing) above) for 2 demo clients ×
  2 demo fiscal years × 1 demo cost system, in both JSON and XML where the
  live endpoint actually supports both (detected from the real response's
  content type, not assumed), into `static-demo/data/`, mirroring the real
  URL paths. Group B write-derived resources are excluded — a fresh
  snapshot would only ever show them empty.
- Deterministic, thanks to [Referential integrity and path-param
  scoping](#referential-integrity-and-path-param-scoping) above: the same
  demo scope always generates the same, internally-consistent data, so
  this snapshot is a faithful mirror, not an approximation — a demo
  creditor's `addressee_id` really does resolve in the demo addressees
  file, same guarantee the live mock gives.
- `static-demo/index.html` is a small, dependency-free Bootstrap page: a
  banner up top spelling out exactly what this is and isn't (static,
  fixed demo ids, no writes, no `Accept`-header negotiation — JSON/XML are
  separate files here) plus how to run the real mock locally instead, and
  a catalog below it (built from `static-demo/data/manifest.json`) to
  browse every snapshotted resource.
- Published via `.github/workflows/gh-pages.yml` (official
  `actions/upload-pages-artifact` + `actions/deploy-pages`, no
  third-party action) on every push touching `static-demo/**`. Requires
  a one-time repo setting (**Settings → Pages → Source: "GitHub
  Actions"**) to actually go live.
- Regenerate after any change to `fake_data.py`'s generation logic:
  `.venv\Scripts\python scripts\generate_static_demo.py` (Windows) /
  `.venv/bin/python scripts/generate_static_demo.py` (Linux/macOS), then
  commit the resulting `static-demo/data/` diff.

### Expand and nested content

`GET .../creditors` and `GET .../debitors` leave `addresses`/`banks`/
`communications`/`accounting_information`/`legal_person`/`natural_person`/
`not_specified_person` nil by default — confirmed real DATEV behavior
(real-data-reconciliation epic), not a gap. Pass `?expand=all` to get them
populated with real, spec-shaped, deterministic content instead (same
scope/id always returns the same expanded content):

```
GET /datev/api/accounting/v1/clients/{client_id}/fiscal-years/{fiscal_year_id}/creditors?expand=all
```

`expand` is the **only** query parameter this mock reads and acts on —
`select`/`filter`/`skip`/`top` are still uniformly ignored (this project's
established "support a query param only when a real consumer needs it"
principle; every other documented DATEV query param has never had a
concrete consumer ask for it).

This epic also fixed genuine bugs found via a real integration client:
several generated timestamps (and the shared `_random_timestamp()` helper
behind most of this mock's dates) were missing their RFC3339 zone offset
(`"...T00:00:00.000"` instead of `"...T00:00:00.000+01:00"`), and a couple
of `DebitorAccountingInformation` enum fields used invented placeholder
values instead of DATEV's real spec-declared members — both harmless to
most JSON consumers, but a strict Java client's generated model rejects
either outright. Fixed at the source; every generated timestamp now
includes the offset, every enum field now only emits real spec values.

### Legacy vs. modern DATEV API version

`cost-centers` has one field, `cost_rates[].valid_from`/`valid_to`, that's
genuinely integer-encoded dates per DATEV's own official spec (confirmed
directly against `Accounting-1.5.0.json` — not a bug). A real integration
client built against ELO's older internal reference mock (which never
sent this field at all) rejects it anyway. Rather than choose one
behavior, the admin UI's **Settings** card has a **DATEV API version**
toggle:

- **Legacy** (the default) — `cost-centers` omits `cost_rates` entirely,
  matching that older reference mock's shape.
- **Modern** — the full, spec-accurate `CostCenter` including
  `cost_rates`.

Same mechanism as `default_accounting_format`: persisted in
`settings.json`, changeable via the admin UI or
`PUT /admin/api/settings`, takes effect on the next request (no restart
needed). Defaults to *legacy* because that's what this mock's actual
local integration testing has needed working out of the box — switch to
*modern* to exercise the complete, spec-accurate contract instead.

### Trusting the mock's TLS certificate (Java / enterprise HTTP clients)

The mock's self-signed certificate (`certs/cert.pem`) is fine for a
browser (accept the one-time warning) or `curl -k`, but a strict Java
HTTP client — the kind generated for enterprise integrations like ELO's
DATEV connector — validates the certificate chain by default and will
fail with something like:

```
javax.net.ssl.SSLHandshakeException: PKIX path building failed:
sun.security.provider.certpath.SunCertPathBuilderException: unable to
find valid certification path to requested target
```

even with a client-side "trust all hosts/certificates" toggle enabled, if
that toggle doesn't actually cover the code path making the request. The
reliable fix is importing the mock's certificate directly into the
JVM's truststore the integration client actually runs on:

1. **Start the mock at least once** so `certs/cert.pem` exists (`start.sh`/
   `start.bat` generate it on first run if missing).
2. **Find the JVM your integration client uses** — not necessarily your
   system `java`; an enterprise product often ships its own bundled
   runtime (e.g. `<product-install-dir>\java\bin\java.exe`). Confirm its
   version and locate its truststore, normally at
   `<that-jvm-dir>/lib/security/cacerts` (default password `changeit`
   unless the product changed it).
3. **Import the certificate** (`keytool` ships with every JDK):
   ```bat
   "<jvm-dir>\bin\keytool.exe" -importcert ^
     -keystore "<jvm-dir>\lib\security\cacerts" ^
     -storepass changeit ^
     -alias datev-mock ^
     -file "<path-to-this-repo>\certs\cert.pem" ^
     -noprompt
   ```
   (`keytool` prints a warning suggesting its newer `-cacerts` convenience
   flag — don't combine it with an explicit `-keystore`, they conflict;
   the explicit `-keystore` form above works on every JDK version.)
4. **Restart the service/process that embeds that JVM** — a truststore is
   read once at JVM startup, so an already-running process won't pick up
   the new entry until it's restarted.
5. **Point the client at `https://` on this mock's port** (not `http://`
   — TLS is mandatory here, matching the real DATEV Desktop API; see
   [Quick start](#quick-start) for the `DATEV_MOCK_HTTP=1` escape hatch
   if TLS trust genuinely can't be arranged for a given client).

To verify the import worked without restarting anything yet:
```bat
"<jvm-dir>\bin\keytool.exe" -list -keystore "<jvm-dir>\lib\security\cacerts" -storepass changeit -alias datev-mock
```

### Settings & admin UI

`https://127.0.0.1:58452/admin` — a Bootstrap 5 in-browser page with:

- **Settings** — change the **port** and the **default response format**
  for `accounting/v1/clients` (`xml`/`json`). The format change applies
  immediately (used whenever a request's `Accept` header doesn't explicitly
  ask for one or the other — an explicit `Accept: application/xml` or
  `Accept: application/json` always wins regardless of this setting). The
  port change is persisted but only takes effect on the **next restart** —
  a running server can't rebind its own port live (the page shows a clear
  notice when this applies).
- **Editable datasets** — view, add, edit, and delete the mock's fictitious
  master-data (18 records) and accounting (100 records) client records
  directly, plus reset both lists back to their generated defaults. Edits
  are in-memory for the life of the process — gone on restart (by design;
  only settings persist to disk, in a git-ignored `settings.json`). This
  applies to these two admin-editable tables specifically, not to the mock
  as a whole any more — the newer write endpoints (`POST`/`PUT` on
  debitors, creditors, and the other resources listed under [Write
  endpoints and persistence](#write-endpoints-and-persistence)) are
  SQLite-backed and **do** survive a restart, by design; see that section
  for the distinction.
  Each table also has **Export CSV** (downloads the current records —
  useful as a template, since it shows exactly which columns a re-import
  understands) and **Import CSV** (adds many records in one upload instead
  of one at a time; only the columns the "Add ..." form already supports
  are used — `Name`/`Number`/`Status`/`Type` for master-data, `Name`/
  `Number` for accounting — anything else in the file, like an exported
  `Id` or `company_data.*` column, is ignored; failed rows are skipped and
  counted rather than aborting the whole import).
- **API Catalog** — a browsable, accordion-grouped reference covering
  **all 23 mocked read-only endpoints** (Diagnostics, Base clients, Master
  Data, Accounting, DMS), not just the 2 editable tables above — the 26
  newer write endpoints aren't in this catalog yet, out of scope for that
  epic. Each entry shows
  its HTTP method, the real path with illustrative path-parameter values
  resolved (this mock ignores their actual values by design — any value
  works), an on-demand "View sample data" fetch with two tabs — **Table**
  (rows/columns, for both JSON and XML responses — XML is parsed
  client-side into the same row/column view, not just shown as raw text)
  and **Raw** (the full response body, syntax-highlighted via
  [highlight.js](https://highlightjs.org/) — CDN, XML and JSON both
  supported) — and a "Copy curl" button that builds a ready-to-run example
  using the live-configured port. Nothing in the catalog fetches
  automatically on page load.
- **Custom Examples (Overrides)** — upload your own XML or JSON file (one
  at a time, or **an entire folder at once** via the folder-picker "Import
  Folder" button — every `.xml`/`.json` file in it is uploaded and matched
  the same way, with a summary of how many matched, need manual
  disambiguation, or weren't recognized) and the mock automatically detects
  which endpoint each one matches, then serves it
  verbatim for that endpoint until you disable or delete it. See
  [Custom overrides](#custom-overrides) below for the full detail.

Same JSON API backing the two editable tables is also usable directly
(`GET`/`PUT /admin/api/settings`,
`GET/POST/PUT/DELETE /admin/api/clients/{master-data,accounting}[/{id}]`,
`POST /admin/api/reset`) if you want to script dataset setup for a test run.

### Custom overrides

Upload a file in the admin page's "Custom Examples" card and the mock
inspects its structure to figure out which of the 22 override-eligible
endpoints it belongs to — no manual endpoint selection needed in the
common case:

- **XML**: matched by root element (e.g. `Echo`, `ArrayOfClientResource`,
  `ArrayOfClient`, `ArrayOfDebitor`, `ArrayOfOpenItem` — one per XML-capable
  endpoint).
- **JSON**: matched by a field-name fingerprint (e.g. a record with
  `bic`+`country_code` is recognized as `banks`; `account_number`+
  `caption`+`main_function` as `general-ledger-accounts`, etc.).

Three groups of endpoints are **genuinely structurally identical** to each
other (confirmed against DATEV's own OpenAPI specs) and can't be told
apart from shape alone: creditors/debitors, accounts-payable/
accounts-payable-condense/accounts-receivable-condense, and
posting-proposal-rules-incoming/outgoing-invoices. Uploading a file
matching one of these shows all the matching candidates and asks you to
pick — deliberately, rather than guessing wrong.

Once matched (automatically or by your pick), the override is **active
immediately** — a confirmation shows which endpoint it's serving *and* the
real, clickable URL (with the live-configured port) so you can try it
right away. Toggle it off any time to fall back to the mock's normal
generated data without losing the uploaded file, or delete it outright.
Everything is in-memory
only (never written to disk) and resets on restart, same as the editable
datasets above (this in-memory-only behavior is specific to overrides and
the 2 editable datasets — it does not extend to the newer, SQLite-backed
write endpoints; see [Write endpoints and
persistence](#write-endpoints-and-persistence)). An active override always
wins over `accounting/v1/clients`'s usual `Accept`-header negotiation — it
serves exactly what you uploaded, in the format you uploaded it in.

Full write-up: [`odd/tasks/datev-mock-custom-overrides.md`](odd/tasks/datev-mock-custom-overrides.md).

#### Using real DATEV data as an override

For maximum realism you can capture a genuine response from a real DATEV
installation and upload that instead of a hand-written example.

**A clarification before you do**: there is no single public "test" or
"production" URL to document for this — unlike DATEV's cloud *Online APIs*
(which do have hosted OAuth endpoints), the *local Desktop API* this mock
replicates is a service that only runs on-prem, wherever your
organization's DATEV Arbeitsplatz software is installed, reachable only
from that local network. The only real address in this project is the one
already noted in [Switching between mock and real
DATEV](#switching-between-mock-and-real-datev) below —
`https://192.168.0.13:58452` — which is *this specific project's* real
workstation, not a general DATEV URL. In your own environment, substitute
your own DATEV workstation's actual host/IP and port.

1. From a machine with network access to that real DATEV installation,
   request the endpoint whose response you want to capture (browser,
   `curl`, or Postman all work) — for this project's own real workstation,
   those three base endpoints were:
   `https://192.168.0.13:58452/datev/api/master-data/v1/clients`,
   `https://192.168.0.13:58452/datev/api/diagnostics/v1/echo`, and
   `https://192.168.0.13:58452/datev/api/accounting/v1/clients` — replace
   `192.168.0.13` with your own DATEV workstation's actual host/IP.
2. Authenticate when prompted. Per DATEV's own documentation for this API
   family, the local Desktop API accepts **Basic**, **Windows**, or
   **OpenID Connect** authentication — whichever your installation is
   configured for; use your normal DATEV Arbeitsplatz credentials.
3. Save the response body to a local `.xml` or `.json` file (browser:
   "Save as"; `curl`: `curl -k -o clients.xml -u <user> https://...`,
   adapting the auth flag to your environment's method).
4. Open this mock's `/admin` page → **Custom Examples (Overrides)** →
   upload that saved file. It's auto-detected and activated immediately —
   see [Custom overrides](#custom-overrides) above.

⚠️ Real captured DATEV data is sensitive, same as
[`examples/`](examples/) in this repo — never commit it, and handle it per
your organization's data policy. This mock keeps overrides in-memory only
and never writes them to disk, but the saved file itself lives on your
machine until you delete it.

### Switching between mock and real DATEV

The mock runs on the exact same port and path structure as the real local
API. Switching is just a base-URL config change in whatever application
consumes the API — **no hosts file edit, no DNS changes, no admin rights**:

- Real: `https://192.168.0.13:58452`
- Mock: `https://127.0.0.1:58452`

## Project structure

```
DATEV-Mock/
├── app/
│   ├── main.py
│   ├── routers/
│   │   ├── diagnostics.py
│   │   ├── master_data.py   # clients/addressees/employees (read + write) + banks
│   │   ├── accounting.py    # 15 sub-resources (read) + 26 write endpoints, all XML/JSON where modeled
│   │   ├── dms.py           # domains/documents (JSON, self-designed schema)
│   │   └── admin.py         # settings + dataset CRUD + overrides + logs + stored-records + the /admin page
│   ├── models.py
│   ├── write_models.py      # Pydantic request-body models for the 26 write endpoints
│   ├── db.py                # SQLite persistence (one generic `stored_records` table)
│   ├── request_log.py       # live request/response log: ring buffer, SSE, CLI logging, unmatched-route detection
│   ├── xml_serializers.py
│   ├── json_serializers.py  # accounting.clients + master_data.clients JSON projections
│   ├── fake_data.py         # seeded generators for every resource
│   ├── data_store.py        # mutable in-memory store the routers read from
│   ├── config.py            # Settings (port, default format), settings.json persistence
│   └── overrides.py         # custom XML/JSON upload detection + in-memory override store
├── certs/                   # self-signed cert generation (generate_cert.py; *.pem is git-ignored)
├── examples/                 # local-only, git-ignored — sensitive real captured samples + the internal-mock reference doc
├── odd/tasks/
│   ├── datev-mock.md                       # base API: epic/task tracking, decisions, progress log
│   ├── datev-mock-settings.md              # settings/admin UI: same, for that epic
│   ├── datev-mock-extended-endpoints.md    # 20 extended endpoints: same, for that epic
│   ├── datev-mock-admin-ui-polish.md       # Bootstrap redesign + full catalog: same, for that epic
│   ├── datev-mock-custom-overrides.md      # upload/override system: same, for that epic
│   ├── datev-mock-real-data-reconciliation.md  # reconciled every endpoint against real DATEV data: same, for that epic
│   └── datev-mock-write-endpoints-and-observability.md  # 26 write endpoints + SQLite + live log: same, for that epic
├── tests/                     # full test suite — 375/375 passing
├── start.bat / start.sh       # bootstrap Python (portable if needed) + deps + run, one step
├── settings.json              # git-ignored, created on first settings change
├── datev_mock.db              # git-ignored, created on first write to any of the 26 new write endpoints
└── requirements.txt
```

## Setup

Requires Python 3.12+.

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Running the tests

```
.venv\Scripts\python -m pytest tests/ -v
```

All 375 tests pass.

## Running the server

Easiest: `start.bat` (Windows) / `./start.sh` (Linux/macOS) — see
[Quick start](#quick-start) above. Manually:

```
.venv\Scripts\python certs\generate_cert.py
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 58452 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
```

Swagger UI: `https://127.0.0.1:58452/docs`. Admin/settings UI:
`https://127.0.0.1:58452/admin`. Both verified live over real HTTPS,
including the accounting endpoint's XML/JSON content negotiation.

## Technology

| | |
|---|---|
| **Language / runtime** | Python 3.12+ |
| **Web framework** | [FastAPI](https://fastapi.tiangolo.com/) on [Uvicorn](https://www.uvicorn.org/) (ASGI) |
| **Testing** | [pytest](https://pytest.org/) + FastAPI's `TestClient` (Starlette/httpx) |
| **Frontend (admin UI)** | [Bootstrap 5](https://getbootstrap.com/) (CDN) + vanilla JS — no build step, no framework dependency |
| **Syntax highlighting** | [highlight.js](https://highlightjs.org/) (CDN, cdnjs) — raw XML/JSON view in the API Catalog |
| **TLS** | Self-signed cert generated with the [`cryptography`](https://cryptography.io/) package |
| **File uploads** | [`python-multipart`](https://pypi.org/project/python-multipart/) (FastAPI's multipart/form-data parsing, used by the custom-overrides upload) |
| **Serialization** | Hand-built XML (stdlib string templates, matching .NET `DataContractSerializer` conventions) + native JSON |
| **Persistence** | In-memory data store for the 2 editable datasets and overrides (per-process, reset on restart) + stdlib `sqlite3` (no ORM) for the 26 write endpoints, in a git-ignored `datev_mock.db` that survives a restart + a small git-ignored `settings.json` for port/format preferences |
| **Bootstrap scripts** | Batch (`start.bat`) / POSIX shell (`start.sh`) — provision a project-local Python (system if available, else a portable download) with no admin rights |

