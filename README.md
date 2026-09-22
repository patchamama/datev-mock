# DATEV Desktop API Mock

A local FastAPI mock of DATEV's local Desktop API (the REST interface a DATEV
workstation normally exposes on `https://<local-ip>:58452/datev/api/...`),
built for developing and testing against DATEV integrations without a real
DATEV installation.

It reproduces the exact response shapes of the endpoints used during real
capture, and additionally supports the response format documented on DATEV's
official developer portal where the two disagree (see
[Key decisions](#key-decisions) below).

## Status

**GREEN — implemented and passing.** All 165 tests pass
(`.venv\Scripts\python -m pytest tests/ -v`), and the server has been
verified live over real HTTPS on port 58452 (all 24 mocked endpoints, the
admin UI, and Swagger UI). Three epics complete:
[`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (base API),
[`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md)
(settings/admin UI), and
[`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md)
(21 additional endpoints: Master Data addressees/banks, 15 Accounting
sub-resources, DMS). See each task doc for full breakdowns, decisions, and
progress logs.

## Quick start

No Python installed? These scripts bootstrap a project-local Python (system
Python if available, otherwise a portable download into this folder — no
system-wide install, no admin rights), install dependencies, generate the
HTTPS cert, and start the server:

- Windows: `start.bat`
- Linux/macOS: `./start.sh`

Then open `https://127.0.0.1:58452/admin` (accept the self-signed cert
warning once) or `https://127.0.0.1:58452/docs` for Swagger.

## Endpoints mocked

**Base API** (real-capture XML, base project — see
[Key decisions](#key-decisions)):

| Method | Path | Format |
|---|---|---|
| `GET` | `/datev/api/diagnostics/v1/echo` | XML |
| `GET` | `/datev/api/master-data/v1/clients` | XML |
| `GET` | `/datev/api/accounting/v1/clients` | XML (default) **or** JSON (`Accept: application/json`) |

All three match the real .NET `DataContractSerializer` XML conventions
(root element names, namespaces, `i:nil="true"` for null fields) observed in
real captured traffic used locally for shape reference only. That capture
contains sensitive real-environment data and is **not** included in this
repository (kept local-only, git-ignored) — no real values from it are
reused anywhere in the mock's data, only field shapes.

**Extended endpoints** (JSON-only — no real XML evidence exists for any of
these, only JSON evidence from DATEV's official OpenAPI specs and a
separate internal reference mock; see
[Extended endpoint sourcing](#extended-endpoint-sourcing) below):

| Area | Endpoints |
|---|---|
| Master Data | `GET /master-data/v1/addressees`, `GET /master-data/v1/addressees/{addressee-id}` (real 404-on-unknown-id lookup), `GET /master-data/v1/banks` |
| Accounting | `GET /accounting/v1/clients/{client-id}/fiscal-years`, and under `.../fiscal-years/{fiscal-year-id}/`: `cost-systems` (+`cost-systems/{id}/cost-centers`), `creditors`, `debitors`, `general-ledger-accounts`, `accounts-payable` (+`/condense`), `accounts-receivable/condense`, `accounting-sequences-processed`, `accounting-transaction-keys`, `assets/stocktakings`, `posting-proposal-rules-incoming-invoices`, `posting-proposal-rules-outgoing-invoices`, `terms-of-payment` |
| DMS | `GET /dms/v1/domains`, `GET /dms/v1/documents` — **self-designed schema**, no official spec exists for this area at all (see caveat below) |

None of the extended endpoints filter by their path parameters (`client-id`/
`fiscal-year-id`/`cost-system-id` are accepted but ignored — every call
returns the same fake dataset) except the one noted 404 lookup, which
mirrors observed real behavior. Query params (`select`/`filter`/`skip`/
`top`/`expand`) are documented by DATEV but not implemented anywhere in this
mock — out of scope until an actual consumer needs them.

## Key decisions

### XML vs JSON on `accounting/v1/clients`

Two sources disagree on this endpoint:

- **Real captured traffic** (local-only, not in this repo): XML, port 58452,
  HTTPS.
- **Official DATEV developer docs** (developer.datev.de, Accounting product
  v1.7.4): JSON, port 58454, plain HTTP — confirmed example:
  ```json
  [{"company_data":{"creditor_identifier":"DE98ZZZ09999999999"},"id":"78a11a29-2a32-4a5e-a73b-632f6aeae131","name":"DATEVconnect GmbH","number":"47011"}]
  ```

**Decision: support both**, via `Accept`-header content negotiation on the
*same* port (58452) — no second port binding. `Accept: application/xml` (or
no preference) returns the XML shape; `Accept: application/json` returns the
documented JSON shape, including its `number`-as-string quirk (preserved
faithfully, not coerced to an int like the XML `Number`).

Master Data and Diagnostics remain **XML-only** — there is no confirmed
official JSON spec for those two, so none was invented. Documented
OData-style query params (`select`, `filter`, `skip`, `top`, `expand`) are
explicitly out of scope for now.

Full write-up: [`odd/tasks/datev-mock.md` → "Decisions"](odd/tasks/datev-mock.md#decisions).

### Extended endpoint sourcing

The 21 extended endpoints (everything beyond the original 3) were scoped
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
- **DMS (domains, documents)**: **no official spec exists** for this area
  at all (confirmed by exhaustive search) — the schema is self-designed
  from two one-line descriptions in an internal reference doc ("domain/
  folder/register tree" and "document metadata including amount, class,
  GUIDs, and timestamps"). Lower fidelity than everything else in this
  mock, by necessity, not oversight — treat DMS responses as illustrative
  shape only, not a verified DATEV contract.

Full write-up: [`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md).

### Settings & admin UI

`https://127.0.0.1:58452/admin` — a simple in-browser page to:

- Change the **port** and the **default response format** for
  `accounting/v1/clients` (`xml`/`json`). The format change applies
  immediately (used whenever a request's `Accept` header doesn't explicitly
  ask for one or the other — an explicit `Accept: application/xml` or
  `Accept: application/json` always wins regardless of this setting). The
  port change is persisted but only takes effect on the **next restart** —
  a running server can't rebind its own port live.
- **View, add, edit, and delete** the mock's fictitious master-data and
  accounting client records directly, plus reset both lists back to their
  generated defaults. Edits are in-memory for the life of the process —
  they're gone on restart (by design; only settings persist to disk, in a
  git-ignored `settings.json`).

Same JSON API backing the page is also usable directly (`GET`/`PUT
/admin/api/settings`, `GET/POST/PUT/DELETE /admin/api/clients/{master-data,accounting}[/{id}]`,
`POST /admin/api/reset`) if you want to script dataset setup for a test run.

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
│   │   ├── master_data.py   # clients (XML) + addressees/banks (JSON)
│   │   ├── accounting.py    # clients (XML/JSON) + 15 sub-resources (JSON)
│   │   ├── dms.py           # domains/documents (JSON, self-designed schema)
│   │   └── admin.py         # settings + dataset CRUD + the /admin page
│   ├── models.py
│   ├── xml_serializers.py
│   ├── json_serializers.py  # accounting JSON path only
│   ├── fake_data.py         # seeded generators for every resource
│   ├── data_store.py        # mutable in-memory store the routers read from
│   └── config.py            # Settings (port, default format), settings.json persistence
├── certs/                   # self-signed cert generation (generate_cert.py; *.pem is git-ignored)
├── examples/                 # local-only, git-ignored — sensitive real captured samples + the internal-mock reference doc
├── odd/tasks/
│   ├── datev-mock.md                     # base API: epic/task tracking, decisions, progress log
│   ├── datev-mock-settings.md            # settings/admin UI: same, for that epic
│   └── datev-mock-extended-endpoints.md  # 21 extended endpoints: same, for that epic
├── tests/                     # full test suite — 165/165 passing
├── start.bat / start.sh       # bootstrap Python (portable if needed) + deps + run, one step
├── settings.json              # git-ignored, created on first settings change
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

All 165 tests pass.

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

## Tasks / Roadmap

Three epics, all complete (165/165 tests). See each task doc for full
detail, decisions, and progress logs:

**Base API** — [`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (32 tests):
- [x] T0–T7 — RED-phase tests → models → fake data → XML/JSON serializers →
      routers → README → GREEN verification.

**Settings & admin UI** — [`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md) (45 more tests):
- [x] S0–S7 — RED-phase tests → `config.py` (port/format persistence) →
      mutable data store → `/admin/api/*` CRUD → admin HTML page → live
      content-negotiation wiring → this README section → GREEN
      verification.

**Extended endpoints** — [`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md) (88 more tests):
- [x] Phase A — Master Data addressees/banks (3 endpoints)
- [x] Phase B — Accounting sub-resources (15 endpoints, split into two
      delivery batches)
- [x] Phase C — DMS domains/documents (2 endpoints, self-designed schema)
- [x] D0 — this README update

Nothing further is currently planned — the admin UI's dataset editor still
covers only the original master-data/accounting clients lists, not the 21
extended-endpoint resources; that would be a new decision if it's ever
wanted.
