# DATEV Desktop API Mock

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pytest](https://img.shields.io/badge/tests-212%20passing-brightgreen?logo=pytest&logoColor=white)](tests/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Status](https://img.shields.io/badge/status-active-success)](#tasks--roadmap)

A local FastAPI mock of DATEV's local Desktop API (the REST interface a DATEV
workstation normally exposes on `https://<local-ip>:58452/datev/api/...`),
built for developing and testing against DATEV integrations without a real
DATEV installation.

It reproduces the exact response shapes of the endpoints used during real
capture, and additionally supports the response format documented on DATEV's
official developer portal where the two disagree (see
[Key decisions](#key-decisions) below).

## Contents

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
- [Tasks / Roadmap](#tasks--roadmap)

## Status

**GREEN — implemented and passing.** All 212 tests pass
(`.venv\Scripts\python -m pytest tests/ -v`), and the server has been
verified live over real HTTPS on port 58452 (all 23 mocked endpoints, the
Bootstrap admin UI with its full endpoint catalog and custom-override
uploads, and Swagger UI). Five epics complete:
[`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (base API),
[`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md)
(settings/admin UI),
[`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md)
(20 additional endpoints: Master Data addressees/banks, 15 Accounting
sub-resources, DMS),
[`odd/tasks/datev-mock-admin-ui-polish.md`](odd/tasks/datev-mock-admin-ui-polish.md)
(Bootstrap admin UI + full endpoint catalog), and
[`odd/tasks/datev-mock-custom-overrides.md`](odd/tasks/datev-mock-custom-overrides.md)
(upload a custom XML/JSON example to temporarily override any endpoint's
response). See each task doc for full breakdowns, decisions, and progress
logs.

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
- **DMS (domains, documents)**: **no official spec exists** for this area
  at all (confirmed by exhaustive search) — the schema is self-designed
  from two one-line descriptions in an internal reference doc ("domain/
  folder/register tree" and "document metadata including amount, class,
  GUIDs, and timestamps"). Lower fidelity than everything else in this
  mock, by necessity, not oversight — treat DMS responses as illustrative
  shape only, not a verified DATEV contract.

Full write-up: [`odd/tasks/datev-mock-extended-endpoints.md`](odd/tasks/datev-mock-extended-endpoints.md).

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
  only settings persist to disk, in a git-ignored `settings.json`).
- **API Catalog** — a browsable, accordion-grouped reference covering
  **all 23 mocked endpoints** (Diagnostics, Base clients, Master Data,
  Accounting, DMS), not just the 2 editable tables above. Each entry shows
  its HTTP method, the real path with illustrative path-parameter values
  resolved (this mock ignores their actual values by design — any value
  works), an on-demand "View sample data" fetch with two tabs — **Table**
  (rows/columns for JSON responses) and **Raw** (the full response body,
  syntax-highlighted via [highlight.js](https://highlightjs.org/) — CDN,
  XML and JSON both supported) — and a "Copy curl" button that builds a
  ready-to-run example using the live-configured port. Nothing in the
  catalog fetches automatically on page load.
- **Custom Examples (Overrides)** — upload your own XML or JSON file and
  the mock automatically detects which endpoint it matches, then serves it
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

- **XML**: matched by root element (`Echo`, `ArrayOfClientResource`,
  `ArrayOfClient` — the only 3 XML shapes this mock has).
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
immediately** — a badge confirms which endpoint it's serving. Toggle it
off any time to fall back to the mock's normal generated data without
losing the uploaded file, or delete it outright. Everything is in-memory
only (never written to disk) and resets on restart, same as the editable
datasets above. An active override always wins over `accounting/v1/clients`'s
usual `Accept`-header negotiation — it serves exactly what you uploaded,
in the format you uploaded it in.

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
│   │   ├── master_data.py   # clients (XML) + addressees/banks (JSON)
│   │   ├── accounting.py    # clients (XML/JSON) + 15 sub-resources (JSON)
│   │   ├── dms.py           # domains/documents (JSON, self-designed schema)
│   │   └── admin.py         # settings + dataset CRUD + overrides + the /admin page
│   ├── models.py
│   ├── xml_serializers.py
│   ├── json_serializers.py  # accounting JSON path only
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
│   └── datev-mock-custom-overrides.md      # upload/override system: same, for that epic
├── tests/                     # full test suite — 212/212 passing
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

All 212 tests pass.

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
| **Persistence** | In-memory data store (per-process, reset on restart) + a small git-ignored `settings.json` for port/format preferences |
| **Bootstrap scripts** | Batch (`start.bat`) / POSIX shell (`start.sh`) — provision a project-local Python (system if available, else a portable download) with no admin rights |

## Tasks / Roadmap

All five epics complete (212/212 tests). See each task doc for full
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

**Admin UI overhaul & documentation polish** — [`odd/tasks/datev-mock-admin-ui-polish.md`](odd/tasks/datev-mock-admin-ui-polish.md):
- [x] Bootstrap 5 redesign of `/admin`, plus a full read-only catalog
      covering all 23 mocked endpoints (not just the 2 CRUD-editable
      tables) — each entry shows its HTTP method, resolved example path,
      a "view sample data" action, and a copyable `curl` example.
- [x] README polish pass (badges, technology table, table of contents,
      this roadmap section).
- [x] Follow-on: `start.bat`/`start.sh` auto-open the browser at `/admin`
      on launch; `/docs` link and real-endpoint labels added to the admin
      page; official DATEV documentation links added where a confirmed
      URL exists (Master Data, Accounting — Diagnostics/DMS intentionally
      left unlinked, no confirmed docs found for either).

**Custom example overrides** — [`odd/tasks/datev-mock-custom-overrides.md`](odd/tasks/datev-mock-custom-overrides.md):
- [x] `app/overrides.py` — structural detection (XML root tag / JSON field
      fingerprint) matching an uploaded file to one of 22 override-eligible
      endpoints, with honest multi-candidate handling for the 3 endpoint
      groups that share an identical schema.
- [x] `/admin/api/overrides*` — upload, ambiguity resolution, list,
      enable/disable, delete.
- [x] Wired into all 22 real endpoint handlers — an active override is
      served verbatim, bypassing normal generation and (for
      `accounting/v1/clients`) `Accept`-header negotiation.
- [x] Admin UI: upload form, candidate-picker for ambiguous matches, and
      an overrides table with per-row enable/disable and delete.
- [x] This README update.

### Planned / not started

- **Java port** — build an equivalent mock as a Java application (mirroring
  the tech stack of the internal reference mock this project's extended
  endpoints were gap-analyzed against, see
  [`examples/DATEV_Mock_Server_Reference.md`](examples/DATEV_Mock_Server_Reference.md),
  local-only). Not scoped or started — recorded here as a future
  possibility, not a commitment.
- Full CRUD (not just read-only display) for the 20 extended-endpoint
  resources in the admin UI, if ever needed for interactive test-data
  shaping beyond the existing master-data/accounting clients tables.
