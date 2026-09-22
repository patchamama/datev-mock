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

**GREEN — implemented and passing.** All 77 tests pass
(`.venv\Scripts\python -m pytest tests/ -v`), and the server has been
verified live over real HTTPS on port 58452 (all 3 mocked endpoints, the
admin UI, and Swagger UI). See
[`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (base API) and
[`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md)
(settings/admin UI) for the full task breakdowns, decisions, and progress
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

| Method | Path | Source contract | Format |
|---|---|---|---|
| `GET` | `/datev/api/diagnostics/v1/echo` | `Echo` (`Datev.ApplicationHost.Server.DataObjects`) | XML |
| `GET` | `/datev/api/master-data/v1/clients` | `ArrayOfClientResource` (`Datev.Sdd.Connect.PlugIn.Contracts.Resources`) | XML |
| `GET` | `/datev/api/accounting/v1/clients` | `ArrayOfClient` (`Datev.Irw.Connect.Accounting.Contracts.Clients`) | XML (default) **or** JSON (`Accept: application/json`) |

All responses match the real .NET `DataContractSerializer` XML conventions
(root element names, namespaces, `i:nil="true"` for null fields) observed in
real captured traffic used locally for shape reference only. That capture
contains sensitive real-environment data and is **not** included in this
repository (kept local-only, git-ignored) — no real values from it are
reused anywhere in the mock's data, only field shapes.

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
│   │   ├── master_data.py
│   │   ├── accounting.py
│   │   └── admin.py         # settings + dataset CRUD + the /admin page
│   ├── models.py
│   ├── xml_serializers.py
│   ├── json_serializers.py  # accounting JSON path only
│   ├── fake_data.py         # seeded generators
│   ├── data_store.py        # mutable in-memory store the routers read from
│   └── config.py            # Settings (port, default format), settings.json persistence
├── certs/                   # self-signed cert generation (generate_cert.py; *.pem is git-ignored)
├── examples/                 # local-only, git-ignored — sensitive real captured samples
├── odd/tasks/
│   ├── datev-mock.md          # base API: epic/task tracking, decisions, progress log
│   └── datev-mock-settings.md # settings/admin UI: same, for that epic
├── tests/                     # full test suite — 77/77 passing
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

All 77 tests pass.

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

See [`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) (base API, 32
tests) and [`odd/tasks/datev-mock-settings.md`](odd/tasks/datev-mock-settings.md)
(settings/admin UI, 45 more tests) for the complete task lists, decisions,
and progress logs. Both epics are complete:

**Base API:**
- [x] T0–T7 — RED-phase tests → models → fake data → XML/JSON serializers →
      routers → README → GREEN verification. See task doc for detail.

**Settings & admin UI:**
- [x] S0–S7 — RED-phase tests → `config.py` (port/format persistence) →
      mutable data store → `/admin/api/*` CRUD → admin HTML page → live
      content-negotiation wiring → this README section → GREEN
      verification. See task doc for detail.

A gap-analysis reference against a separate existing internal DATEV mock
(19 additional endpoints across fiscal-years, cost-systems, creditors/
debitors, general-ledger-accounts, DMS, addressees, banks, etc.) exists for
future scope decisions but is explicitly out of scope for now.
