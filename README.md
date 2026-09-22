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

**GREEN — implemented and passing.** All 32 tests pass
(`.venv\Scripts\python -m pytest tests/ -v`), and the server has been
verified live over real HTTPS on port 58452 (all 3 endpoints + Swagger UI).
See [`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) for the full task
breakdown, decisions, and progress log.

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
│   │   └── accounting.py
│   ├── models.py
│   ├── xml_serializers.py
│   ├── json_serializers.py # accounting JSON path only
│   └── fake_data.py
├── certs/                  # self-signed cert generation (generate_cert.py; *.pem is git-ignored)
├── examples/                # local-only, git-ignored — sensitive real captured samples
├── odd/tasks/datev-mock.md # epic/task tracking, decisions, progress log
├── tests/                   # full test suite — 32/32 passing
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

All 32 tests pass.

## Running the server

```
.venv\Scripts\python certs\generate_cert.py
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 58452 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
```

Swagger UI: `https://127.0.0.1:58452/docs`. Verified live over real HTTPS,
including the accounting endpoint's XML/JSON content negotiation and
Swagger UI itself.

## Tasks / Roadmap

See [`odd/tasks/datev-mock.md`](odd/tasks/datev-mock.md) for the complete
task list, decisions, and progress log. Summary — all complete:

- [x] T0 — RED-phase test suite (32 tests across diagnostics, master-data,
      accounting XML, accounting JSON)
- [x] T1 — Project scaffold (`app/` package, self-signed cert generation)
- [x] T2 — Data models (`ClientResource` 42 fields, accounting `Client`,
      `Echo`)
- [x] T3 — Synthetic fake data generation (no real values)
- [x] T4 — XML serializers (all 3 shapes) + JSON serializer for accounting
- [x] T5 — FastAPI routers + content negotiation for accounting
- [x] T6 — This README
- [x] T7 — GREEN verification (32/32 passing + live HTTPS/Swagger sanity
      check on port 58452)
