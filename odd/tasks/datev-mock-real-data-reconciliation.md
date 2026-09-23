# DATEV Mock — Reconciliation Against Real Captured Data

## Objective
The user captured real responses from their own DATEV Desktop API
installation (using `test-datev.html`, their own credentials, never shared
with the assistant) for most of the extended-endpoints epic's 15 accounting
sub-resources plus addressees/master-data-clients/echo. Files live in
`examples/` (local-only, git-ignored, real business data — **shape only is
used here, no real values are ever copied into this repo's code, tests, or
fake data generators**). Compare the mock's current behavior against this
real evidence and reconcile — full scope (campos completos + soporte XML
paralelo en los 15), per user decision 2026-09-23.

**Source files** (all local-only under `examples/`, referenced by name only
in this doc — never quote their real content verbatim beyond field names/
types): `cost-systems.xml`, `debitors.xml` (real XML), `addressees.xml`,
`creditors.xml`, `general-ledger-accounts.xml`, `condense.xml` (accounts-
payable/condense), `accounts-receivable-condense.xml`,
`accounting-sequences-processed.xml`, `accounting-transaction-keys.xml`,
`fiscal-years.xml`, `terms-of-payment.xml`, `posting-proposal-rules-
{incoming,outgoing}-invoices.xml` (both empty `[]` — legitimately no data
configured, not an error), `master-data-clients.xml` (JSON variant),
`echo.xml`, `accounting-clients.xml`, plus a compiled first-record summary
at `examples/examples-summary.txt` (local-only). DMS confirmed **absent**:
both `dms/v1/domains` and `dms/v1/documents` return `{"error":"Domäne
'dms' mit der Version 'v1' ist in keinem der geladenen PlugIns", ...}` —
i.e. the plugin isn't loaded in this installation.

## Key findings

1. **Content negotiation is universal, not accounting/clients-specific.**
   Real evidence: `debitors` came back as **XML** (`ArrayOfDebitor` /
   `Debitor`, PascalCase, `.NET DataContractSerializer` conventions
   identical to the original 3 endpoints) while `creditors` — same system,
   same session — came back as **JSON** (snake_case). `master-data/clients`
   also has a JSON variant (7 flat fields) alongside its known 42-field XML.
   **Decision: add the same XML/JSON content-negotiation this mock already
   has for `accounting/clients` to all 15 accounting sub-resources and to
   `master-data/clients`.** XML shape for endpoints without direct real XML
   evidence is **inferred by the same consistent pattern** observed in
   every confirmed case (`ArrayOf<Name>` root, `<Name>` repeated child,
   namespace `http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.
   Accounting.Contracts.<Name>`, PascalCase field names matching the real
   JSON field names 1:1) — flagged per-endpoint below as "confirmed" vs
   "inferred by pattern," never presented as more certain than it is.

2. **Several "quirks" this project deliberately preserved are contradicted
   by real evidence and must be corrected, not preserved:**
   - `accounting.clients` JSON `number` is a **real integer** (e.g.
     `10015`), not a string. The official-docs example (`"number":"47011"`)
     this project's earlier decision was based on appears stale/inaccurate.
     **Fix: change `number` to an int in the JSON serializer.**
   - `general_ledger_accounts.main_function`/`main_function_number` include
     **`0`** as a real observed value — not in this project's hardcoded
     `[1..7]`/`[10,11,12,20,21,25,90,91,98]` lookup sets. **Fix: add `0` to
     both sets** (keep them as hardcoded lookups — still no OpenAPI enum —
     just correct the value ranges).
   - `accounts_receivable_condense.dunning_level` (this project's own
     invented field, explicitly flagged as "RED-imposed, not spec-derived"
     at the time) **does not exist** in real data. The real, analogous
     field is `has_dunning_block` (boolean) — a different concept.
     **Fix: remove `dunning_level`, add `has_dunning_block`** (see field
     table below for `OpenItem`'s full real shape).
   - DMS has no path forward to "correct" (no real evidence beyond
     confirming it's absent in this installation) — leave as-is
     (self-designed, already clearly flagged in README/task docs), no
     change needed here.

3. **Real field sets are substantially larger than this project's current
   models** for nearly every resource — see table below.

## Real field tables (top-level fields only; shape/types, never real values)

### `fiscal_years` (JSON confirmed; XML inferred by pattern)
Current model has 9 fields. Real: `id`, `account_length` (int),
`account_system` (int), `advance_turnover_tax_return` (str, e.g. a
cadence keyword), `basis_of_checking_account_function` (str, optional —
absent on some records), `begin`/`end` (ISO datetime with timezone offset,
**two separate fields**, not implied by a single one), `client_number`
(int), `consultant_number` (int), `cost_length` (int),
`creditor_term_of_payment_id` (int), `currency_code` (str),
`debitor_term_of_payment_id` (int, optional — absent on some records),
`is_invoice_date_check_on` (bool), `is_locked` (bool),
`is_using_delivery_date` (bool), `is_using_individual_referencesystem`
(bool), `is_using_receivable_type` (bool), `is_using_referencesystem`
(bool), `legal_form` (str, optional), `method_of_determining_net_income`
(str, optional), `national_right` (str), `taxation_method` (str). 24
fields total, several genuinely optional (absent, not null, on some
records — the existing "absent from JSON = optional" convention already
established for this project applies).

### `cost_systems` (XML **confirmed** real — this is the ground truth, not JSON)
Real XML root `ArrayOfCostSystems`, repeated child `CostSystems` (note:
**plural**, not singular `CostSystem` as this project currently emits).
Fields (PascalCase, XML): `Id`, `Parent` (nil), `membersToSerialize` (nil),
`CostField` (int-as-text — **not** `IsActivatedForPostings`'s neighbor
`CostField` that this project doesn't have at all today), `IsActivatedForPostings`
(bool-as-text), `Number` (int-as-text), `ShortName` (str). JSON field-name
equivalents (snake_case, by the same 1:1 convention every other endpoint
uses): `id`, `cost_field`, `is_activated_for_postings`, `number`,
`short_name`. **This project's current model is missing `cost_field`
entirely** and currently omits the XML path altogether.

### `creditors` (JSON confirmed) / `debitors` (XML confirmed — same logical resource, both formats real)
Real JSON (`creditors`) top-level fields: `account_number` (int),
`addressee_id` (str/uuid), `business_partner_number` (str),
`business_partner_relation_id` (str/uuid), `caption` (str),
`date_last_modification` (ISO datetime w/ tz), `eu_vat_id_country_code`
(str, optional), `eu_vat_id_number` (str, optional), `id`,
`is_business_partner_active` (bool), `is_organization_business_partner`
(bool), `legal_entity_type` (str enum), `short_name` (str). 13 fields —
notably **no `natural_person`/`legal_person` nested sub-objects appear at
all** in the observed real record (this project invented those as nested
objects; real data may omit them entirely at this top level, or they may
require `expand=all` per the official docs' own documented query param —
which this project has deliberately not implemented). **Decision: drop the
invented `natural_person`/`legal_person`/`not_specified_person` nested
sub-objects from the default (non-expanded) response — they were never
observed and the docs suggest they're an `expand`-only detail this mock
doesn't implement.** Real XML (`debitors`) confirms the same field set
(PascalCase) plus reveals the **full list of nested/optional fields this
project never modeled**: `AccountingInformation`, `Addresses`,
`AlternativeSearchName`, `Banks`, `Communications`, `ComplimentaryClose`,
`CorrespondenceTitle`, `NaturalPerson`, `LegalPerson`, `NotSpecifiedPerson`,
`Salutation`, `ThirdPartyNumber` — all **nil** in the observed real record.
Model these as always-nil/absent-by-default fields (matching real
sparsity), not populated ones — consistent with this project's existing
"match the real sparsity pattern" philosophy for the base 3 endpoints.

### `general_ledger_accounts` (JSON confirmed)
Real fields: `account_number` (int), `additional_function` (int, observed
value `0`), `caption` (str), `function_extension` (int, observed `0` —
**field this project doesn't have at all**), `id`, `main_function` (int,
observed `0`), `main_function_number` (int, observed `0`). Add
`function_extension`; correct `main_function`/`main_function_number`
lookup sets to include `0`.

### `accounts_payable`/`accounts_payable_condense` (JSON confirmed via `condense.xml`) and `accounts_receivable_condense` (JSON confirmed)
Shared real fields (both): `account_number` (int), `accounting_sequence_id`
(str), `balancing_type` (str enum), `contra_account_number` (int), `date`
(ISO datetime w/ tz), `debit_credit_identifier` (str, `"S"`/`"H"` as
already known), `document_field1`/`document_field2` (str), `evidence_type`
(str enum), `has_dunning_block` (bool), `has_interest_block` (bool), `id`,
`is_cleared` (bool), `is_condensed` (bool), `kost1_cost_center_id` (str),
`open_balance_of_item` (float), `open_item_number` (str), `payment_method`
(str enum), `posting_description` (str), `posting_record_number` (**int**,
confirmed unquoted in both real capture files — W3), `tax_rate` (float).

**W3 correction (supersedes the paragraph below, kept only for history):**
this table originally claimed `amount_credit` is payable-only and
`amount_debit`/`due_date`/`due_days`/`term_of_payment_id` are
receivable-only, based on a single first-record summary. W3 counted real
field occurrences directly across the full capture files
(`examples/condense.xml`, 3642 records; `examples/accounts-receivable-
condense.xml`, 3455 records) and found this wrong:
`amount_debit`/`amount_credit` are **mutually exclusive per record** on
**both** payable and receivable (driven by `debit_credit_identifier`
S/H — counts sum to the total record count on both sides), and
`due_date`/`due_days`/`term_of_payment_id` are present on ~49% of records
on **both** sides (not receivable-only). Payable and receivable are, in
practice, the **same** schema (aside from `dunning_date1/2/3`, kept
receivable-only per this project's pre-existing design — zero real
evidence either way in either file). `OpenItem` needed ~19 always-present
+ several evidenced-optional fields, not ~9. Remove the invented
`dunning_level`; use `has_dunning_block` instead (done in W1).

~~Payable-side observed `amount_credit` (float); receivable-side observed
`amount_debit` (float) plus 3 receivable-only fields: `due_date`
(ISO datetime w/ tz), `due_days` (int), `term_of_payment_id` (int). This
confirms payable and receivable are NOT byte-identical schemas in
practice — receivable has 3 extra fields.~~ (superseded above — kept
struck through for history, not for the field shape).

Keep them in the same override-detection "ambiguous group" regardless
(the shared subset is still what makes them indistinguishable from a
fingerprint alone — this doesn't change the override epic's design, just
the model completeness).

### `accounting_sequences_processed` (JSON confirmed)
Real fields: `accounting_reason` (str enum), `accounting_sequence_id`
(str), `date_committed` (ISO datetime w/ tz), `date_from`/`date_to` (ISO
datetime w/ tz), `description` (str), `id`, `inspection_status` (str enum
— new field), `is_committed` (bool), `mark_of_origin` (str — new field,
short code), `record_type` (str enum). Add `date_committed`,
`inspection_status`, `mark_of_origin`.

### `accounting_transaction_keys` (JSON confirmed)
Real fields: `additional_function` (str enum — **this project modeled it
as absent entirely**), `caption` (str), `cases_related_to_goods_and_services`
(int), `date_from`/`date_to` (ISO datetime w/ tz), `group` (str — category
label), `id`, `is_tax_rate_selectable` (bool), `number` (int), `tax_rate`
(float). Add `additional_function`, `caption`, `cases_related_to_goods_and_services`,
`date_from`, `date_to`, `group`.

### `addressees` (JSON confirmed, top-level only — no `detail` sub-object observed)
Real top-level fields across the full 111-record sample: `company_names`
(historical array), `current_company_name`, `current_legal_form_id`,
`current_short_name`, `current_surname`, `date_of_birth` (natural_person
only), `date_of_foundation` (legal_person only — **new field**),
`eu_vat_id_country_code`, `eu_vat_id_number`, `firstname`, `id`,
`legal_form_ids` (historical array), `sex`, `short_names` (historical
array), `status`, `surnames` (historical array — **this project's
fingerprint/model uses a flat `surnames` field, not this historical-array
shape with `{value}` elements**), `surrogate_name`, `timestamp`, `type`.
Confirms the "historical field" pattern from the official Client Master
Data docs (`current_X` scalar + `X` array-of-`{value[, valid_from]}`)
genuinely applies here — model `company_names`/`short_names`/
`legal_form_ids`/`surnames` as that array shape, not flat strings.

### `terms_of_payment` (JSON confirmed) — already matches
Real: `caption`, `due_in_days: {due_in_days}`, `due_type`, `id`. This
project's current model already matches this shape exactly — no change
needed here beyond adding the XML negotiation path.

### `posting_proposal_rules_incoming`/`outgoing` — no new evidence
Both returned `[]` (legitimately no rules configured for this client) —
confirms the endpoints exist and return a bare JSON array as expected, but
provides no field-shape evidence beyond what's already modeled. No changes
to the field model; still add the XML negotiation path (inferred by
pattern, same as fiscal_years/cost_centers/etc. that also lack direct XML
evidence).

### `master_data.clients` — new JSON variant discovered
Real JSON (in addition to the already-modeled 42-field XML): `id`,
`legal_person_id`, `name`, `number` (int), `status`, `timestamp`, `type` —
7 flat fields, clearly a simplified projection of the full XML shape, not
a fully independent schema. **Decision: add a JSON path for
`master_data.clients` using exactly these 7 fields** (derived from the
existing XML-backing dataclass's same-named fields — not a new fake-data
generator, just a projection/serializer, matching how `accounting.clients`
already derives its JSON view from the same underlying records as its XML
view).

### `echo` — no shape change, confirms existing JSON path already correct
Real JSON matches this project's already-existing assumption exactly
(`echo_message`, `id`) — no change needed. (Interesting operationally: the
real system returned JSON for `echo` in this capture despite no explicit
`Accept: application/json`, and XML in the original capture that seeded
this whole project — reinforces that this system's default format is
inconsistent/state-dependent across calls, not a fixed default. This
mock's own default-format `Accept`-driven negotiation design already
handles this correctly either way — no action needed, just noted as
external-system behavior, not something to replicate.)

### `cost_centers` — no new evidence
Not captured in this round (needs a real `cost-system-id`, which requires
first calling `cost_systems`). No changes — existing model stands until
evidence arrives.

## Cross-cutting decisions
- XML negotiation pattern for all 15: reuse the exact mechanism already
  built for `accounting.clients` (`Accept: application/json` → JSON,
  `Accept: application/xml` or ambiguous → XML, explicit header always
  wins). Root tag / namespace per endpoint: `ArrayOf<PascalName>` /
  `http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.
  Contracts.<PascalName>`, following the two directly-confirmed examples
  (`cost-systems`→`CostSystems`, `debitors`→`Debitor`) — apply the same
  naming convention per-endpoint (check each one's natural PascalCase
  form, don't blindly template).
- Override-detection (`app/overrides.py`) fingerprints and the 3 ambiguous
  groups from the earlier custom-overrides epic remain valid — field sets
  are being *expanded*, not renamed, so existing fingerprint field-name
  requirements still match (verify this holds per-endpoint during
  implementation, flag any conflict rather than assuming).
- No changes to `examples/` handling — stays local-only, git-ignored,
  shape-only reference, exactly as already established.

## Tasks
- [x] W1 — RED+GREEN: quick, isolated quirk fixes (accounting.clients
      `number` as int, general_ledger_accounts `main_function`/
      `main_function_number` include 0, replace `dunning_level` with
      `has_dunning_block`, remove creditor/debitor's invented nested
      person sub-objects from the default response).
- [x] W2 — RED+GREEN batch A: expand fields + add XML negotiation for
      `fiscal_years`, `cost_systems` (rename repeated element to
      `CostSystems`, add missing `cost_field`), `cost_centers` (XML
      negotiation only, no field changes — no new evidence), `creditors`,
      `debitors`, `general_ledger_accounts`.
- [x] W3 — RED+GREEN batch B: expand fields + add XML negotiation for
      `accounts_payable`, `accounts_payable_condense`,
      `accounts_receivable_condense` (incl. the 3 receivable-only fields),
      `accounting_sequences_processed`, `accounting_transaction_keys`.
- [ ] W4 — RED+GREEN batch C: expand `addressees` (historical-array
      fields, `date_of_foundation`, `sex`), add XML negotiation for
      `posting_proposal_rules_incoming`/`outgoing` and `terms_of_payment`
      (no field changes needed for the latter), add the new JSON
      projection for `master_data.clients`.
- [ ] W5 — Full regression + README/task-doc updates reflecting the
      corrected understanding (content negotiation is universal, not
      accounting/clients-specific; note the quirk corrections and why).
- [ ] W6 — Commit + push (likely per-batch, matching the standing
      "commit+push when a phase finishes" workflow, given the size).

## Route
Every batch: delegated direct (each touches models.py, fake_data.py,
xml_serializers.py or a new json/xml split per endpoint, the relevant
router, and tests — well over the Writer trigger). Orchestrator verifies
and commits after each batch, same discipline as every prior epic.

## Progress
- 2026-09-23: Epic created from real captured evidence (local-only files in `examples/`, shape-only reference). User chose full-scope reconciliation (complete fields + XML negotiation for all 15). Starting with W1 (quick quirk fixes).
- 2026-09-23: W1 done (RED+GREEN, delegated direct). All 4 quirk fixes applied against real captured evidence; 232/232 tests passing (same count as before — existing tests' assertions were corrected, no new endpoints added). Route: delegated direct (touched `app/json_serializers.py`, `app/fake_data.py`, `app/models.py`, and 4 test files — over the Writer trigger).
  - **Fix 1 — `accounting.clients` JSON `number` as int**: `app/json_serializers.py::serialize_clients_json` changed `"number": str(record.Number)` to `"number": record.Number`. Real evidence: `examples/accounting-clients.xml` (JSON content) shows `number` as a real JSON integer (not a quoted string) on every sampled record, confirmed by direct read. Updated `tests/test_accounting_json.py::test_accounting_json_record_has_id_name_number` (now asserts `int`, was `str`) and renamed/inverted `test_accounting_json_number_is_not_coerced_to_int` → `test_accounting_json_number_is_a_real_int_not_a_string` (now asserts `isinstance(..., int)` and `not isinstance(..., str)`, the exact opposite of its old assertion) — this test previously explicitly guarded the old, now-known-wrong string behavior; corrected per real evidence, not preference.
  - **Fix 2 — `general_ledger_accounts.main_function`/`main_function_number` include `0`**: `app/fake_data.py`'s `_MAIN_FUNCTION_VALUES`/`_MAIN_FUNCTION_NUMBER_VALUES` widened to include `0` (kept as hardcoded lookups, still no OpenAPI enum). Real evidence: grepped `examples/general-ledger-accounts.xml` (JSON content) — every sampled record showed `"main_function":0` and `"main_function_number":0`. Updated `tests/test_accounting_misc.py`'s module-level `_MAIN_FUNCTION_VALUES`/`_MAIN_FUNCTION_NUMBER_VALUES` sets (used by `test_general_ledger_account_main_function_values_use_hardcoded_lookup_range`) to include `0`, matching the widened valid-value sets.
  - **Fix 3 — replace invented `dunning_level` with real `has_dunning_block`**: `app/models.py::OpenItem` dropped `dunning_level: Optional[str]`, added `has_dunning_block: bool = False`; `app/fake_data.py::_generate_open_items` now populates `has_dunning_block` on every record (both `receivable=True` and `receivable=False`), not just receivable ones. Real evidence: grepped both `examples/accounts-receivable-condense.xml` and `examples/condense.xml` (both JSON content) — `has_dunning_block":false` appears repeatedly in both files; zero matches for `"dunning_level"` in either. Updated `tests/test_accounting_payables_receivables.py::test_accounts_receivable_condense_record_has_core_fields` to assert `isinstance(record.get("has_dunning_block"), bool)` instead of the old `dunning_level` string assertion — this test previously asserted this project's own invented, RED-imposed field; corrected per real evidence. `dunning_date1/2/3` (also receivable-only) were left untouched — no real evidence contradicts them, and full field-expansion is W3 scope, not W1.
  - **Fix 4 — drop invented `natural_person`/`legal_person`/`not_specified_person` from creditors/debitors' default response**: `app/fake_data.py::_generate_creditors`/`_generate_debitors` no longer construct `NaturalPerson`/`LegalPerson` objects or pass them to `Creditor`/`Debitor` (fields stay `None` by default, stripped from JSON by the existing `_strip_none(asdict(...))` path); removed the now-unused `NaturalPerson`/`LegalPerson` imports from `app/fake_data.py`. Model fields (`app/models.py::Creditor`/`Debitor`) were kept (not deleted) since debitors' real XML shows them as always-nil fields, consistent with this project's existing sparsity-modeling convention and useful groundwork for a future `expand=all` W2+ batch. Real evidence: grepped `examples/creditors.xml` (JSON content) — zero matches for `"natural_person":`/`"legal_person":`/`"not_specified_person":` as populated values; grepped `examples/debitors.xml` (real XML) — `NaturalPerson`/`LegalPerson`/`NotSpecifiedPerson` appear only as `i:nil="true"` elements (2397 occurrences, all nil). Updated `tests/test_accounting_partners.py`: renamed/inverted `test_natural_person_creditors_have_representative_fields` → `test_natural_person_creditors_do_not_populate_nested_natural_person` and `test_legal_person_creditors_have_representative_fields` → `test_legal_person_creditors_do_not_populate_nested_legal_person`, both now assert `record.get(...) is None` instead of asserting a populated dict — these tests previously asserted this project's invented default-population behavior; corrected per real evidence.
  - No real captured values (names, account numbers, IDs) were copied into any code or test — only field names, types, and presence/absence shape, verified before each edit.
  - Final: `232 passed, 2 warnings in 2.80s` (pytest tests/ -v). Same total as before W1 — no new endpoints/records added, only existing assertions corrected plus 2 renamed tests (net test count unchanged; renames replace, not add).
- 2026-09-23: W2 done (RED+GREEN, delegated direct). Field expansion + XML/JSON content negotiation added for `fiscal_years`, `cost_systems`, `cost_centers`, `creditors`, `debitors`, `general_ledger_accounts`. 248/248 tests passing (232 + 16 new). Route: delegated direct (touched `app/models.py`, `app/fake_data.py`, `app/xml_serializers.py`, `app/routers/accounting.py`, 3 named test files plus `tests/test_overrides_integration.py` — well over the Writer trigger).
  - **`fiscal_years`**: `FiscalYear` expanded from 9 to 23 real fields (epic doc says "24" but the confirmed real field table only lists 23 distinct names — verified by direct count against `examples/fiscal-years.xml`). Added the 2 fields the model was actually missing (`is_using_individual_referencesystem`, `is_using_referencesystem`); promoted `legal_form` from required to `Optional`; reordered the dataclass so the 19 always-present fields are required (no default) and the 4 genuinely-optional ones (`basis_of_checking_account_function`, `debitor_term_of_payment_id`, `legal_form`, `method_of_determining_net_income`) default to `None`. `_generate_fiscal_years` now leaves each optional field absent on at least one generated record and present on at least one other (matching real sparsity, not just "the type is Optional"). `begin`/`end` gained a `+01:00` timezone-offset suffix matching the real ISO shape (structural only, not a copied value).
  - **`cost_systems`**: `cost_field` corrected from an unevidenced `Optional[str]` to a real, required `int` (confirmed: `examples/cost-systems.xml`, real XML, `CostField` element, int-valued, present on every sampled record) — `_generate_cost_systems` now populates it as a sequential int instead of a `"KOST{n}"` string. XML repeated element name is `CostSystems` (plural, confirmed) — written correctly from the start since no XML path existed for this endpoint before W2.
  - **`cost_centers`**: no field changes (no new evidence, as the epic doc already noted). XML negotiation added only.
  - **`creditors`/`debitors`**: both expanded to the real 13-field shape (11 always-present + `eu_vat_id_country_code`/`eu_vat_id_number` optional). Added `business_partner_relation_id`, `caption`, `date_last_modification`, `is_business_partner_active`, `is_organization_business_partner` as required fields (previously optional/sometimes-unset) and made fake data populate all of them on every record. **Correction beyond the original brief**: the task instructions state `AccountingInformation` "should stay nil-by-default in fake data" alongside `Addresses`/`Banks`/etc. — but the codebase, before this batch, actually *did* populate `accounting_information` on every generated creditor/debitor (with a real object, not nil), which contradicts both the instruction and the real evidence (`examples/debitors.xml` shows `AccountingInformation` always `i:nil="true"`; the real `creditors` JSON sample doesn't carry the field at all). Fixed: `_generate_creditors`/`_generate_debitors` no longer construct `CreditorAccountingInformation`/`DebitorAccountingInformation`; the field now stays `None` (nil in XML, absent in JSON) by default, matching real evidence. Also added 4 previously-unmodeled always-nil fields confirmed by `examples/debitors.xml`'s real XML — `addresses`, `banks`, `communications`, `complimentary_close` — to both `Creditor` and `Debitor` (the task text asserted these already existed in the model; they did not — verified directly against `app/models.py` before adding them).
  - **`general_ledger_accounts`**: added required `function_extension: int` (confirmed: `examples/general-ledger-accounts.xml`, observed value `0` on every sampled record) via a small `_FUNCTION_EXTENSION_VALUES` lookup pool (`0`-dominant, matching evidence, without hardcoding every record to the literal same value). `function_description` (a pre-existing, unconfirmed extra field, not part of the real 7-field shape) made genuinely sparse (absent on one generated record) so the new XML "i:nil for an optional field" test has a real case to exercise — it was previously always populated.
  - **XML negotiation, all 6**: same mechanism as `accounting.clients` (`Accept: application/json` explicit → JSON; `Accept: application/xml` explicit or ambiguous/missing → the live `default_accounting_format` setting, defaulting to `"xml"`), factored into a new `app/routers/accounting.py::_negotiate_format` helper (accounting.clients' own inline copy deliberately left untouched, out of scope). New `app/xml_serializers.py` generic helpers (`_pascal`, `_xml_tag`, `_generic_ns_attr`, `_render_generic_record`) implement the shared `Id`/`Parent`/`membersToSerialize` preamble + alphabetical-PascalCase-order convention observed on **every** confirmed real sample so far (`ClientResource`, `Client`, `CostSystems`, `Debitor` — 4/4). Also fixed `_render_field` to emit lowercase `true`/`false` for booleans (Python's `str(True)` would have emitted the wrong-case `True`; untested before W2 since no prior serialized dataclass had a bool field).
  - **Confirmed vs. inferred XML shape, per endpoint**: `cost_systems` root/namespace/element name — **confirmed** (`examples/cost-systems.xml`). `debitors` root/namespace/field order — **confirmed** (`examples/debitors.xml`); notably its namespace is `...Contracts.BusinessPartners`, not `...Contracts.Debitor` — real evidence that the generic "namespace == singular resource name" pattern isn't universal. `creditors` — **inferred**, reusing debitors' confirmed `BusinessPartners` namespace and field order (same contract family, never directly observed as XML itself). `fiscal_years`, `cost_centers`, `general_ledger_accounts` — **inferred by pattern** (`ArrayOf<PascalName>`/`...Contracts.<PascalName>`, majority convention from the other confirmed samples); their `PascalName` choice (singular) and field order (alphabetical after the preamble) follow the 4/4-confirmed pattern but are not themselves directly evidenced. List-typed fields with zero real XML evidence at all (`cost_centers.cost_rates`/`.properties`, `general_ledger_accounts.tax_rates`) were deliberately **excluded** from the inferred XML shape rather than inventing a nested representation — they stay JSON-only, same precedent as `Client.CompanyData`/`.company_data`.
  - **Test updates beyond the 3 named files**: `tests/test_overrides_integration.py` had 2 bare (no `Accept` header) GETs to the `debitors`/`creditors` endpoints that previously always returned JSON (no negotiation existed); both now explicitly pass `Accept: application/json`, since ambiguous/missing now defaults to XML.
  - **`app/overrides.py` fingerprints**: verified all 5 relevant fingerprints (`fiscal_years`, `cost_systems`, `cost_centers`, the `creditors`/`debitors` ambiguous group, `general_ledger_accounts`) still correctly match the expanded models — every fingerprint's required-field subset is a subset of fields kept required (or still real-evidenced-present) after expansion. No changes made to `app/overrides.py`.
  - Self-check: grepped every changed file for real names/GUIDs/numbers observed while reading `examples/debitors.xml`/`examples/fiscal-years.xml` directly (`Bolz`, `Manuel`, `Atvur`, `Oguzhan`, `Radowski`, `Silvio`, the sampled account numbers/GUIDs, `10015`, `100627`) — zero matches in any code or test file.
  - Live check (port 58459, since 58452 was occupied by the user's own server per the workflow instructions): started `uvicorn`, curled all 6 endpoints with both `Accept: application/xml` and `Accept: application/json` — all 6 returned correct root tags/namespaces (`ArrayOfFiscalYear`, `ArrayOfCostSystems`/`CostSystems` plural, `ArrayOfCostCenter`, `ArrayOfCreditor`, `ArrayOfDebitor`, `ArrayOfGeneralLedgerAccount`) and correct `content-type` per format; default (no `Accept` header) confirmed XML. Stopped via `taskkill //F //PID 2200`; verified port 58459 had no LISTENING socket afterward.
  - Final: `248 passed, 2 warnings in 2.95s` (pytest tests/ -v).
- 2026-09-23: W3 done (RED+GREEN, delegated direct). Field expansion + XML/JSON content negotiation added for `accounts_payable`, `accounts_payable_condense`, `accounts_receivable_condense`, `accounting_sequences_processed`, `accounting_transaction_keys`. 257/257 tests passing (248 + 9 new). Route: delegated direct (touched `app/models.py`, `app/fake_data.py`, `app/xml_serializers.py`, `app/routers/accounting.py`, `app/overrides.py`, 4 test files — well over the Writer trigger).
  - **Correction to this doc's own field table** (see the "W3 correction" note under the `accounts_payable`/`accounts_payable_condense`/`accounts_receivable_condense` section above): the original table, derived from a single first-record summary, wrongly claimed `amount_credit` is payable-only and `amount_debit`/`due_date`/`due_days`/`term_of_payment_id` are receivable-only. Direct occurrence-counting against the full real capture files (`examples/condense.xml`, 3642 records; `examples/accounts-receivable-condense.xml`, 3455 records) showed `amount_debit`/`amount_credit` are mutually exclusive per record on both sides (driven by `debit_credit_identifier`), and `due_date`/`due_days`/`term_of_payment_id` are present at a matching ~49% rate on both sides — payable and receivable are the same schema in practice (aside from pre-existing, unevidenced `dunning_date1/2/3`).
  - **`OpenItem`**: expanded from ~9 fields to real 19 always-present + several evidenced-optional fields (`amount_credit`/`amount_debit`/`balancing_type`/`contra_account_number`/`document_field2`/`due_date`/`due_days`/`kost1_cost_center_id`/`term_of_payment_id`, all `Optional`, matching real presence rates 49%-99% depending on field). `posting_record_number` confirmed real `int` (unquoted in both capture files). Pre-existing unevidenced fields (`amount_entered`, `currency_code`, `assessment_year`, `assigned_due_date`, `balance_type`, `dunning_date1/2/3`) kept untouched, not contradicted by evidence (same precedent as W2's `function_description`). Added `OPEN_ITEM_FIELD_ORDER` (alphabetical PascalCase, inferred convention).
  - **`accounting_sequences_processed`**: added `date_committed` (required), promoted `inspection_status`/`mark_of_origin` optional→required (100% real presence); `initials` (~94% real presence) kept optional; `application_information` (0 real evidence) kept untouched.
  - **`accounting_transaction_keys`**: added `additional_function`, `cases_related_to_goods_and_services`, `date_from`, `date_to`, `group`; promoted `caption` optional→required. All 10 real fields are 100%-present — no optionality for this endpoint.
  - **XML negotiation, all 5**: same `_negotiate_format` mechanism as W2, reused (not duplicated). All 5 endpoints are **inferred by pattern** — no direct real XML evidence exists for any of them (both `condense.xml` variants and the `accounting-sequences-processed.xml`/`accounting-transaction-keys.xml` captures are JSON content despite their `.xml` filenames, same quirk already flagged for `fiscal_years` in W2). `accounts_payable`/`accounts_payable_condense`/`accounts_receivable_condense` all render via one shared `serialize_open_items` (`ArrayOfOpenItem`/`OpenItem`), matching the pre-existing "one shared contract" design of the override ambiguous group.
  - **`app/overrides.py` fingerprint fix**: the open-item ambiguous-group fingerprint required `{amount_debit, amount_credit, evidence_type, debit_credit_identifier}` together — since real evidence now shows `amount_debit`/`amount_credit` are mutually exclusive per record, this fingerprint could never match any real payload (a genuine break, not hypothetical). Replaced with `{evidence_type, debit_credit_identifier, open_balance_of_item, is_condensed}`, 4 fields confirmed present on 100% of records on both sides. Updated `tests/test_overrides.py::test_detect_open_item_fingerprint_is_ambiguous` and `tests/test_overrides_integration.py::test_accounting_accounts_payable_ambiguous_group_resolved_and_served` accordingly; also fixed a bare (no-`Accept`-header) GET in the latter test that broke once `accounts_payable` gained content negotiation defaulting to XML (same fix pattern W2 used for creditors/debitors). `accounting_sequences_processed`/`accounting_transaction_keys` fingerprints needed no changes.
  - Self-check: grepped all 9 changed files for real values observed while reading `examples/condense.xml`/`examples/accounts-receivable-condense.xml`/`examples/examples-summary.txt` directly (real amounts, a real street/name, a real accounting-sequence-id) — zero matches in any committed file. Enum-vocabulary strings used (`mark_of_origin` codes, `group` category labels, `additional_function`/`balancing_type`/`payment_method` values) are DATEV's own closed business vocabulary, not user-specific data — same precedent as the project's existing `_ACCOUNTING_REASON_VALUES`/`_EVIDENCE_TYPE_VALUES` lists.
  - Live check (port 58462): started `uvicorn`, curled all 5 endpoints with both `Accept: application/xml` and `Accept: application/json` plus a default (no-`Accept`) check on `accounts_payable` — all 5 returned correct root tags/namespaces (`ArrayOfOpenItem` x3, `ArrayOfAccountingSequenceProcessed`, `ArrayOfAccountingTransactionKey`) and correct field sets per format; default confirmed XML. Stopped via `taskkill //F //PID 7668`; verified port 58462 had no LISTENING socket afterward. `.gitignore` confirmed untouched (`git diff .gitignore` empty).
  - Final: `257 passed, 2 warnings in 3.15s` (pytest tests/ -q).
