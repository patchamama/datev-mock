# DATEV Mock — real referential integrity + path-param scoping

## Objective

User request (2026-09-24): the mock's fake data has no referential
integrity between resources (e.g. a `Creditor.addressee_id` never matches
any real `Addressee.id`) and every GET route under
`/clients/{client_id}/fiscal-years/{fiscal_year_id}/...` (and
`.../cost-systems/{cost_system_id}/...`) explicitly **ignores** those path
params, always returning the same single global dataset. User confirmed,
via `AskUserQuestion`, the **full scope**: both (a) cross-referenced IDs
should resolve to real records, and (b) path params should actually filter
the returned data — not just (a) alone.

## Research: current state (from a dedicated mapping pass, 2026-09-24)

Full findings in that pass's report (not duplicated verbatim here, this
section is the distilled version the design below is built on):

- `app/fake_data.py` generates **one global dataset, once, at module
  import**, seeded via a single top-level `random.seed(42)`. No generator
  function takes any scoping parameter.
- Every accounting GET route declares `client_id`/`fiscal_year_id`
  [`/cost_system_id`] but never uses them (docstring: "Ignores ...").
  Master-data routes (`clients`, `addressees`, `banks`, `employees`) and
  DMS routes (`domains`, `documents`) are **not** nested under a client
  path at all — nothing to scope there, they stay global.
- Cross-reference audit found exactly **one already-correct pattern**
  (`Document.domain_id` drawn from `Domain`'s own generated id list) and
  three broken patterns used everywhere else: fresh unrelated UUIDs
  (`Creditor/Debitor.addressee_id`), hardcoded/arithmetic values that
  don't match the target's real id scheme
  (`FiscalYear.creditor_term_of_payment_id`,
  `OpenItem.accounting_sequence_id`/`kost1_cost_center_id`/
  `term_of_payment_id`), and coincidental-matching arithmetic that only
  works because two independent generators happen to use the same
  `base + index` formula today (`AssetStocktaking.general_ledger_account`,
  `PostingProposalRule.accounting_transaction_key`/`account_number`,
  `OpenItem.account_number` vs `Creditor`/`Debitor.account_number`) —
  fragile, breaks silently if either side's count/formula changes.
- `app/db.py`'s SQLite half **already has full scoping plumbing**
  (`client_id`/`fiscal_year_id` columns, `list_records()`/
  `delete_records()` already accept and correctly filter by them, unit
  tested) — every write handler already stores these correctly. The only
  gap: `merge_with_stored()` (the function every Group-A GET route calls)
  invokes `list_records(resource_type)` with **no** scope args, and 4
  Group-B routes call `db.list_records(resource_type)` directly, same gap.
  This half is a small, mechanical fix.
- 26 write endpoints; write-side FK-shaped fields fully enumerated in the
  mapping report's table 5 (reused directly in Phase 2 below).
- **15 existing tests directly assert the opposite of the target
  behavior** (`test_*_ignores_path_param_values`-style: two different
  random ids must return identical data) — these are a planned rewrite,
  not an accidental casualty. One write-side test
  (`test_write_endpoints.py:250`,
  `test_put_client_responsibilities_stores_array_without_validating_employee`)
  explicitly encodes today's lack of FK validation and must flip.
- No test fixture establishes "the" client_id/fiscal_year_id/cost_system_id
  — every test file generates fresh random ids inline via a local
  `_fresh_id()` helper. ~175 test functions across 8 files touch these
  endpoints (pool to re-audit, not all individually break).

## Architecture decisions

1. **Deterministic per-scope generation, lenient on unknown IDs — not
   strict hierarchy validation with 404s.** For any `client_id` (and,
   nested, any `fiscal_year_id`, and, nested further, any
   `cost_system_id`), the mock deterministically generates a fresh,
   internally-consistent dataset the *first time* that exact scope key is
   used, then caches it in memory for the process lifetime. Two calls with
   the same scope key always return the same data; two calls with
   different scope keys return different (but each internally coherent)
   data. **No scope key is ever rejected as "unknown"** — every id a
   caller supplies deterministically "exists" the moment it's used.
   Rejected alternative: validating that `fiscal_year_id` belongs to a
   previously-listed set for that `client_id` (404 otherwise) — more
   "realistic" but forces every test/caller to always discover ids via a
   list call first before any nested call works, which is more brittle
   for ad hoc integration testing than what the user actually asked for
   (they asked for *consistency*, not *rejection*). This also sidesteps
   needing to design and test a whole hierarchy-validation/404 subsystem
   the user never explicitly requested.
2. **Seeding**: `_seed_for(*parts: str) -> int` in the new module below —
   `int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:16], 16)`,
   stable across processes (unlike Python's salted `hash()`). A dedicated
   `random.Random(seed)` instance per scope, **never** the shared `random`
   module — every generator function that needs scoped data takes an
   `rng: random.Random` parameter instead of calling the bare `random.*`
   functions. Scope keys: `(client_id,)` for fiscal years,
   `(client_id, fiscal_year_id)` for everything nested one level
   (creditors, debitors, general ledger accounts, cost systems, terms of
   payment, accounting sequences/transaction keys, open items, asset
   stocktakings, posting proposal rules), `(client_id, fiscal_year_id,
   cost_system_id)` for cost centers.
3. **New module `app/scoped_data.py`**, not a rewrite of
   `app/fake_data.py` in place — keeps the existing unscoped generators
   (master-data clients/addressees/banks/employees, DMS domains/documents)
   exactly as they are today in `fake_data.py` (correct already, nothing
   to scope), and adds the new scoped-generation logic for the resources
   that need it, reusing `fake_data.py`'s existing per-record field-shape
   logic where practical (don't duplicate the DATEV field shapes, only
   change *which* ids get cross-referenced and *how* the RNG is sourced).
   Three cache dicts, lazily populated, keyed by the scope tuples above —
   no eviction (this is a local dev mock, not a long-lived production
   service) and, importantly, **no reset needed between tests**: because
   generation is deterministic per scope key, tests that want independent
   data just use a fresh `_fresh_id()` per scope, exactly like they
   already do today — no new autouse fixture required.
4. **Real cross-references, drawn from the actual generated lists, not
   reinvented arithmetic** — replicating the one already-correct existing
   pattern (`Document.domain_id`):
   - `Creditor`/`Debitor.addressee_id` → `rng.choice()` over the **global**
     `Addressee.id` list (master data isn't scoped, so this is the one
     cross-reference that reaches outside the current scope — correctly,
     since addressees are genuinely client-independent in this mock's
     modeling).
   - `FiscalYear.creditor_term_of_payment_id`/`debitor_term_of_payment_id`
     → drawn from that specific fiscal year's own generated
     `TermOfPayment.id` list (requires generating a fiscal year's id
     first, then its nested term-of-payment scope, then backfilling these
     two fields onto the `FiscalYear` record — a small ordering change
     inside fiscal-year generation).
   - `OpenItem.term_of_payment_id` → same-scope `TermOfPayment.id`.
   - `OpenItem.accounting_sequence_id` → same-scope
     `AccountingSequenceProcessed.id`.
   - `OpenItem.kost1_cost_center_id` → the fiscal year's **primary cost
     system** (deterministically index 0 of that scope's generated cost
     systems — `OpenItem` itself has no `cost_system_id` in its own path,
     only `client_id`/`fiscal_year_id`, so it needs one fixed cost system
     to reference) → that cost system's generated `CostCenter.id` list.
     `GET .../cost-systems/{cost_system_id}/cost-centers` still correctly
     returns cost centers for *any* `cost_system_id` passed, independent
     of which one is "primary" for cross-referencing purposes.
   - `AssetStocktaking.general_ledger_account` → same-scope
     `GeneralLedgerAccount` (account_number + caption), drawn from the
     list, not reconstructed via matching arithmetic.
   - `PostingProposalRule.accounting_transaction_key`/`account_number` →
     same-scope `AccountingTransactionKey.number` /
     `GeneralLedgerAccount.account_number`, drawn from the lists.
   - Fields with **no modeled target resource** (`business_partner_relation_id`,
     `LegalPersonId`, and the write-side organization/establishment/
     functional-area id triads) are explicitly left as synthetic/unlinked
     — noted with a short code comment each, not silently ignored.
5. **`app/db.py` fix — the cheap half.** `merge_with_stored()` and the 4
   Group-B `db.list_records()` call sites in `app/routers/accounting.py`
   start forwarding `client_id=client_id, fiscal_year_id=fiscal_year_id`
   (already-tested filtering logic in `db.py` itself needs zero changes).
6. **Write-side FK validation**, scoped correctly. For each write-body
   field identified as FK-shaped (full list already enumerated in the
   mapping report's table 5 — reused as the Phase 2 checklist), validate
   the referenced id exists in **either** that same request's scope's
   generated dataset **or** has been written via a prior POST to that
   resource type/scope (SQLite) — matching what a subsequent `GET` in the
   same scope would actually show. Invalid reference →
   `422 Unprocessable Entity` with a clear message naming the offending
   field (FastAPI/Pydantic's own convention for business-rule validation
   in this codebase — consistent status code across all 26 endpoints).
   Fields with no modeled target resource are left unvalidated (same
   fields as decision #4's last bullet) — this is a real, documented
   limitation, not an oversight, and should be a one-line code comment at
   each such field rather than silent.
7. **Test suite migration is part of this feature, not cleanup after
   it.** The 15 `test_*_ignores_path_param_values` tests get replaced
   with two things each: a `test_*_same_id_is_stable` (same scope twice →
   identical response — proves caching/determinism) and a
   `test_*_different_id_returns_different_data` (two fresh random scope
   ids → response differs — proves real scoping, not just re-ordering).
   New tests assert the specific cross-references resolve (e.g. fetch a
   creditor, confirm its `addressee_id` appears in the addressees list
   fetched separately). `test_write_endpoints.py`'s
   `test_put_client_responsibilities_stores_array_without_validating_employee`
   flips to asserting a `422` for an unknown `employee_id`, plus a
   companion test proving a *real* `employee_id` (fetched from the
   employees endpoint first) succeeds. Existing write-endpoint tests that
   currently POST arbitrary/bogus FK values must switch to using ids
   fetched from the corresponding GET endpoint first, or to a resource
   generated in the same test's scope.

## Phases

- [x] P0 — Mapping/research pass (this doc's research section).
- [x] P1 — `app/scoped_data.py` core: seeding helper, the three scope
      caches, all scoped generator functions with real
      cross-references (decision #4), wired into every accounting.py GET
      route (client_id/fiscal_year_id/cost_system_id actually used) and
      `app/db.py`'s scope-forwarding fix (decision #5). Master-data/DMS
      routes untouched (already correct, unscoped by design). Existing
      test suite will regress here (expected — P3 fixes it); the
      acceptance bar for P1 is live/manual verification that scoping and
      cross-references work correctly, not a green test suite yet.
- [x] P2 — Write-side FK validation across all 26 write endpoints per
      decision #6 and the mapping report's table 5.
- [ ] P3 — Test suite migration (decision #7): rewrite the 15 "ignores"
      tests, update FK-dependent write tests, add new
      scoping/cross-reference tests. Full regression must be green
      (344 baseline ± the net change from added/removed/rewritten tests,
      accounted for explicitly, not just "still passes").
- [ ] P4 — README/task-doc updates, full live re-verification, commit +
      push per phase (established workflow).

## Route

All phases: delegated direct (each touches many files — generation core,
multiple routers, write models/handlers, several test files — well past
the Writer trigger, and P1 in particular needs the full mapping report's
detail to execute correctly). Orchestrator reviews the diff and verifies
live/via pytest independently after each phase before committing, same
discipline as the write-endpoints and exe-release epics.

## Appendix — write-side FK field checklist (from the P0 mapping pass)

26 write endpoints (19 in `app/routers/accounting.py` + 7 in
`app/routers/master_data.py`). Every write-body field that references
another resource's id, and what it should validate against (P2's
checklist):

| Write model (field) | Used by endpoint(s) | Validate against |
|---|---|---|
| `_BusinessPartnerWriteBase.addressee_id` (shared by `DebitorWrite`/`CreditorWrite`) | POST/PUT debitors, POST/PUT creditors (6 endpoints) | `Addressee.id` (master-data addressees, global) |
| `CreditorAccountingInformationWrite.term_of_payment_id` | POST/PUT creditor (nested) | `TermOfPayment.id` (same scope) |
| `DebitorAccountingInformationWrite.term_of_payment_id` | POST/PUT debitor (nested) | `TermOfPayment.id` (same scope) |
| `AssetStocktakingWrite.general_ledger_account.account_number` | PUT asset-stocktaking | `GeneralLedgerAccount.account_number` (same scope) |
| `AssetStocktakingWrite.kost1_cost_center_id` | PUT asset-stocktaking | `CostCenter.id` (same scope's primary cost system, same convention as `OpenItem` in P1) |
| `ClientResponsibility.employee_id` | PUT client responsibilities | `Employee.id` (master-data employees, global) — today explicitly documented as "not validated"; flips in P2 |
| `ClientResponsibility.client_id` (body field, distinct from the URL's own `client_id`) | PUT client responsibilities | `ClientResource.Id` (master-data client) |
| `CostAccountingRecordWrite.account_number` / `contra_account_number` | POST cost-accounting-record | `GeneralLedgerAccount.account_number` (same scope) |
| `CostAccountingRecordWrite.alternative_cost_center` / `cost_center` | POST cost-accounting-record | `CostCenter.id` (same scope) |
| `VariousAddressWrite.account_number` | POST various-address | `Creditor.account_number` OR `Debitor.account_number` (same scope, either family) |
| `VariousAddressWrite.business_partner_number` | POST various-address | `Creditor.business_partner_number` OR `Debitor.business_partner_number` (same scope) |
| `InternalCostServiceWrite.cost_center_from` / `cost_center_to` (both required) | POST internal-cost-service | `CostCenter.id` (same scope) |
| `IncomingInvoicePostingWrite.accounting_transaction_key` | POST posting-proposals-incoming batch | `AccountingTransactionKey.number` (same scope) |
| `IncomingInvoicePostingWrite.account_number` | same | `GeneralLedgerAccount.account_number` (same scope) |
| `IncomingInvoicePostingWrite.creditor_account_number` | same | `Creditor.account_number` (same scope) |
| `IncomingInvoicePostingWrite.kost1_cost_center_id` / `kost2_cost_center_id` | same | `CostCenter.id` (same scope) |
| `OutgoingInvoicePostingWrite.accounting_transaction_key` | POST posting-proposals-outgoing batch | `AccountingTransactionKey.number` (same scope) |
| `OutgoingInvoicePostingWrite.account_number` | same | `GeneralLedgerAccount.account_number` (same scope) |
| `OutgoingInvoicePostingWrite.debitor_account_number` | same | `Debitor.account_number` (same scope) |
| `OutgoingInvoicePostingWrite.kost1_cost_center_id` / `kost2_cost_center_id` | same | `CostCenter.id` (same scope) |
| `CashRegisterPostingWrite.accounting_transaction_key` | POST posting-proposals-cash-register batch | `AccountingTransactionKey.number` (same scope) |
| `CashRegisterPostingWrite.cash_account_number` (required) / `contra_account_number` | same | `GeneralLedgerAccount.account_number` (same scope) |
| `CashRegisterPostingWrite.kost1_cost_center_id` / `kost2_cost_center_id` | same | `CostCenter.id` (same scope) |

**No modeled target resource — leave unvalidated, one code comment each**
(per decision #4/#6's carve-out): `_BusinessPartnerWriteBase.business_partner_relation_id`;
`ClientWrite.legal_person_id`/`natural_person_id`/`organization_id`/`establishment_id`/`functional_area_id`;
`EmployeeWrite.natural_person_id`/`organization_id`/`establishment_id`/`functional_area_id`.

**No FK-shaped fields at all — no P2 work needed**: `TermOfPaymentWrite`,
`CostCenterWrite`, `AddresseeWrite`, `CostCenterPropertyWrite`,
`CostSequenceWrite`, `AccountingSequenceCreateWrite` (6 of the 26
endpoints).

Validate against **the union of the request's own scope's generated data
(`app/scoped_data.py` accessors) and whatever's been written via SQLite
for that same scope** — i.e. exactly what a subsequent `GET` in the same
scope would show, per decision #6.

## Progress

- 2026-09-24: Feature doc created from the dedicated mapping pass.
  Architecture decisions above are the orchestrator's own design call
  (the user authorized full scope via `AskUserQuestion` but left the
  "strict validation vs. lenient deterministic" implementation choice to
  the orchestrator — decision #1 records why lenient was chosen).
- 2026-09-24: P1 done (delegated direct). New `app/scoped_data.py`
  (seeding, 3 scope caches, cross-references per decision #4), `rng`
  threaded through the relevant `app/fake_data.py` generators (backward
  compatible — every new param defaults so unscoped call sites are
  byte-identical to before), all 15 Group-A GET routes + 4 Group-B routes
  in `app/routers/accounting.py` rewired, `app/db.py`'s
  `merge_with_stored()` scope-forwarding fix. One judgment call beyond
  the doc's explicit decision #4 list: 5 generators with no built-in
  randomness (`cost_systems`, `general_ledger_accounts`,
  `terms_of_payment`, `accounting_sequences_processed`,
  `accounting_transaction_keys`) gained `rng`-guarded variation too, so
  all of them (not just the ones with explicit cross-references) genuinely
  differ per scope — matches decision #1's intent, documented in
  `scoped_data.py`'s own module docstring.
  Orchestrator independently re-verified: read `scoped_data.py` in full
  (309 lines) plus the `db.py`/`accounting.py` diffs, re-ran
  `pytest tests/ -q` (329 passed, 15 failed — exactly the 15
  `*_ignores_*`-style tests predicted, zero collateral damage; `tests/`
  itself untouched per `git diff --stat -- tests/`). Committed as
  `9eedb1a`, pushed.
- 2026-09-24: P2 done (delegated direct). Write-side FK validation across
  22 of 26 write endpoints (the other 4 have no FK-shaped fields, per the
  Appendix). Reused `db.merge_with_stored` for every candidate set
  (scope-generated ∪ SQLite-stored) rather than querying SQLite directly.
  One real int/str type gotcha handled: `TermOfPayment.id` is `str` but
  the write-body `term_of_payment_id` fields are `int` — a small
  `_as_int`/`_int_candidates` best-effort-coercion helper fixes this
  (every other cross-referenced pair was already type-matched). Batch
  endpoints (posting-proposals ×3) validate every item before writing
  any of them — no partial writes on a bad batch item.
  `put_client_responsibilities`' `employee_id`/`client_id` now validate
  against global master-data employees/clients, flipping the previously
  documented "not validated" behavior on purpose (decision #6).
  Orchestrator independently re-verified: read the full diff across all 3
  touched files (`write_models.py`'s comment-only changes,
  `master_data.py`'s new helpers + `put_client_responsibilities`,
  `accounting.py`'s shared helpers + every touched write handler),
  re-ran `pytest tests/ -q` (326 passed, 18 failed — exactly P1's 15 plus
  3 new FK-validation-driven failures the agent flagged in advance as
  expected: `test_put_client_responsibilities_stores_array_without_validating_employee`
  and 2 `test_write_endpoints_group_b.py` tests that POST bogus FK
  values; `tests/` itself untouched). Committed as `2179193`, pushed.
