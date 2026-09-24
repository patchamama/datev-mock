# DATEV Mock — real nested content for `expand=all` + field-shape audit

## Objective

User request (2026-09-24), found while debugging a real ELO-for-DATEV
integration against this mock: ELO's connector calls `creditors` with
`expand=all&select=id,caption,addresses,eu_vat_id_number,banks,accounting_information`
and fails client-side with a generic Jersey/Jackson `Error reading entity
from input stream`. Three related endpoints show the same symptom:
`general-ledger-accounts` (`select=...,tax_rates`),
`posting-proposal-rules-incoming/outgoing-invoices`
(`select=assignment_criteria,posting_proposal_information`), and
`cost-centers` (separately root-caused already — see below, **not** part
of this epic's fix).

## Root cause (found via live debugging, not guessed)

- **`cost-centers` — already explained, not a mock bug.**
  `CostCenter.cost_rates[].valid_from`/`valid_to` are genuinely
  integer-encoded dates per DATEV's own official spec (`app/models.py`'s
  `CostRate` docstring: "an explicit spec quirk, not a typo"). ELO's
  client can't handle it; that's a real production risk for ELO's
  DATEV connector, not something to change here — flagged to the user
  as a separate finding, out of scope for this epic.
- **`creditors`/`debitors`** — `app/models.py`'s own `Creditor` docstring
  already documents the real gap precisely: `addresses`/`banks`/
  `communications`/`legal_person`/`natural_person`/`not_specified_person`/
  `accounting_information` are **correctly nil by default** (confirmed
  against real DATEV XML captures, real-data-reconciliation epic) but were
  **never implemented for `expand=all`** — the docstring literally says
  "kept only as latent fields for a possible future `expand=all`
  implementation." Their current dataclass types are placeholders
  (`addresses: Optional[str] = None` — a `str`, not a real nested type).
  ELO's connector requests `expand=all` and gets the (correctly) nil
  default instead of expanded content, which its generated model can't
  handle as an empty/absent result for fields it expects populated.
- **`general-ledger-accounts`/`posting-proposal-rules-*`** — no
  equivalent "confirmed nil by real evidence" documentation exists for
  these; their current `tax_rates`/`assignment_criteria`/
  `posting_proposal_information` shapes were invented by this project
  ("inferred by pattern - no direct real XML evidence for this
  endpoint"), not confirmed against either real DATEV captures or the
  official spec's actual field list. Comparing live against the internal
  reference Java mock (`C:\Mockup\serve-0.1-generate.jar`, port 35000,
  built from the same official `Accounting-1.5.0`/`Client Master Data-
  1.6.0` OpenAPI specs) shows a **different field set** for both
  (`posting_proposal_information[].kost1_cost_center_id` and
  `assignment_criteria.goods_and_services` exist there; our
  `accounting_transaction_key`/`account_number`/`name`/`tax_rate` don't
  match) — this needs re-grounding against the **official spec itself**
  (not the Java mock's limited fixture, which is not authoritative either
  — see decision #1), since neither source has been directly confirmed
  for these two resources yet.

## Architecture decisions

1. **Ground every field decision in the official OpenAPI spec, not the
   Java reference mock's fixture data.** The Java mock's own dataset is a
   limited fixture (e.g. zero `tax_rates`/`cost_rates` records, a
   different and possibly older/incomplete field set for
   `posting_proposal_information`) — matching it would trade fidelity to
   the *real* documented DATEV contract for compatibility with one old
   test client's limited exposure. Re-extract and read
   `Accounting-1.5.0.json` fresh (`"C:\ELO\java\bin\jar.exe" xf
   "C:\Mockup\serve-0.1-generate.jar" "main/mockdata/apispec/Accounting-1.5.0.json"`)
   for `GeneralLedgerAccount`, `PostingProposalRule`/
   `PostingProposalInformation`/`AssignmentCriteria`, and the
   `expand=all` creditor/debitor sub-schemas
   (`Addresses`/`Banks`/`Communications`/`LegalPerson`/`NaturalPerson`/
   `NotSpecifiedPerson`/`CreditorAccountingInformation`/
   `DebitorAccountingInformation`) — resolve exact field names/types/
   `required` flags the same way the extended-endpoints epic's own
   Appendix tables did, don't guess from memory of this conversation's
   earlier partial reads.
2. **`expand=all` becomes a real, implemented query parameter** for
   `creditors`/`debitors` (the first query param this mock will actually
   read and act on — previously all query params were uniformly ignored,
   a deliberate simplicity choice now superseded by real consumer need,
   per this project's own established "support query params only when a
   consumer needs them" principle). Without `expand=all`: unchanged,
   fields stay nil exactly as real DATEV evidence confirms. With
   `expand=all`: populate `addresses`/`banks`/`communications`/
   `legal_person` **or** `natural_person` **or** `not_specified_person`
   (this project's existing "no real polymorphism, pick one" convention
   — reuse it) with real generated content, and `accounting_information`
   too. Other query params (`select`/`filter`/`skip`/`top`) stay ignored
   for now — out of scope, no consumer need demonstrated yet for those
   specifically (decision to revisit only if a future consumer needs
   them, same principle).
3. **Real nested types, not placeholder `str` fields.** Promote
   `addresses`/`banks`/`communications` from `Optional[str]` to properly
   typed lists (`Optional[list[Address]]` etc.) with a new `Address`
   dataclass (`Bank` already exists in `app/models.py`; a `Communication`
   dataclass needs creating) — field shapes resolved from the spec per
   decision #1, not invented.
4. **Deterministic generation, consistent with the referential-integrity
   epic.** Nested address/bank/communication/person content for a given
   creditor/debitor is generated from that same record's scope-seeded
   `rng` (already threaded through `app/scoped_data.py`/
   `app/fake_data.py`'s generators from the prior epic) — same creditor
   id in the same scope always gets the same expanded content, not
   re-randomized per request.
5. **XML rendering must actually work this time** — the earlier "force-
   nil" choice was partly a workaround for nested content rendering as a
   broken Python `repr()` string in XML (write-endpoints epic, P2 notes).
   `app/xml_serializers.py` needs real recursive dataclass-to-XML
   rendering for these nested types (reuse whatever pattern already
   renders `TaxRate`/`GeneralLedgerAccountMinimal` or DMS's nested
   structures correctly, if one already exists — check before writing a
   new one). JSON needs no equivalent fix (`dataclasses.asdict()` already
   recurses correctly into nested dataclasses for JSON).
6. **`general-ledger-accounts`/`posting-proposal-rules-*` field-shape
   correction** happens independently of the `expand=all` work (these
   endpoints don't currently use `expand` at all in ELO's requests) —
   whatever decision #1's fresh spec read reveals as the *real* field set
   replaces the current invented one, cross-checked against the
   `select=...` field lists ELO's live requests actually named (captured
   in this conversation's live debugging — `tax_rates` for GL-accounts;
   `assignment_criteria`/`posting_proposal_information` for posting-
   proposal-rules) as a sanity check that the spec-grounded shape at
   least contains what a real consumer expects.

## Phases

- [x] P1 — Research: fresh official-spec extraction and field-shape
      resolution for all 3 endpoint families (decision #1). Durable
      output: an Appendix in this doc (same convention as this project's
      other epics), not just an agent's transient report.
- [x] P2 — `creditors`/`debitors` `expand=all`: new/promoted dataclasses
      (`Address`, `Communication`, promoted `addresses`/`banks`/
      `communications` types), scoped-deterministic generation, query-
      param-aware router logic, working XML + JSON rendering.
- [x] P3 — `general-ledger-accounts`/`posting-proposal-rules-*` field-
      shape correction per P1's findings.
- [x] P4 — Test suite updates (new `expand=all` coverage; updated shape
      assertions for GL-accounts/posting-proposal-rules where fields
      change) + full regression + live verification against the actual
      query strings ELO sent + README updates + commit/push per phase.

## Route

All phases: delegated direct (spec extraction/reading, multiple model/
serializer/router files, deterministic generation wiring, tests — well
past the Writer trigger). Orchestrator reviews and verifies live after
each phase before committing, same discipline as every other epic this
session.

## Progress

- 2026-09-24: Feature doc created from live ELO-integration debugging in
  this session's conversation (not a cold-start guess) — the `cost-
  centers` root cause, the `creditors`/`debitors` `expand=all` gap
  (already half-documented in `app/models.py`'s own docstrings before
  this epic), and the GL-accounts/posting-proposal-rules field-shape
  uncertainty were all found via direct comparison against the running
  reference Java mock (port 35000) and ELO's own live captured request
  query strings. User explicitly chose full spec-grounded implementation
  over matching the Java mock's limited shape, via `AskUserQuestion`.
- 2026-09-24: P1 complete — fresh extraction of `Accounting-1.5.0.json`
  from `serve-0.1-generate.jar` (68 schemas), resolved every `$ref` chain
  for the creditor/debitor `expand=all` sub-schemas, `general-ledger-
  account`/its `tax_rates` item schema, both `posting-proposal-rule-*`
  variants and their `assignment_criteria`/`posting_proposal_information`
  sub-schemas, and `datev.cost-rate`. Headline results: `CostRate`'s
  integer-date docstring claim is **confirmed** verbatim by the spec (no
  `app/` edit made — see Appendix); `PostingProposalRule`/
  `AssignmentCriteria`/`PostingProposalInformation` and
  `GeneralLedgerAccount`/`GeneralLedgerAccountTaxRate` already match the
  spec **field-for-field** (P3 turns out to need no field-shape changes
  for these two resource families, only wiring `select=` support, which
  P1 flags for that phase to re-decide); `Creditor`/`Debitor`'s
  `addresses`/`banks`/`communications` need new nested dataclasses per
  decision #3 (`banks` is a real conflict with the *existing* master-data
  `Bank` dataclass — different schema, see Appendix), and both
  `accounting_information` sub-schemas are missing several spec fields.
  Full field tables in the new Appendix below, handed to P2/P3 as their
  implementation checklist.
- 2026-09-24: P2 complete (delegated direct). New dataclasses per the
  Appendix checklist (`Address`, `AddressUsageType`,
  `BusinessPartnerBank` — deliberately distinct from the existing
  master-data `Bank`, `Communication`, `CommunicationUsageType`,
  `IndividualField`), `CreditorAccountingInformation`/
  `DebitorAccountingInformation` extended to full spec parity (7→14,
  11→35 fields). `addresses`/`banks`/`communications` promoted from
  `Optional[str]` placeholders to real typed lists. `expand=all` wired as
  the first query param this mock actually reads (decision #2), gated at
  serialization in a new `_apply_expand_gate()` — default stays nil
  exactly as before, `expand=all` populates real deterministic
  scope-seeded content. Also fixed the real underlying XML bug
  (`_render_field` fell through to `str(value)` for dataclasses/lists,
  producing raw Python `repr()` inside XML — the actual reason these
  fields were force-nilled in an earlier epic instead of properly
  rendered) via a new recursive `_render_dataclass_fields()` helper.
  Scope calls made and flagged by the implementer (all reasonable, none
  requiring rework): 1 address/bank/communication per record (spec
  doesn't mandate cardinality), no cross-reference from
  `accounting_information.term_of_payment_id` into the scope's own
  terms-of-payment list (nice-to-have, not required), a few
  `DebitorAccountingInformation` enum fields use invented placeholder
  tokens where the Appendix only documented member *counts* not exact
  values (same precedent as this project's existing `Document
  .document_class`).
  Orchestrator independently re-verified: read the full diff across all
  4 files (477 insertions), re-ran `pytest tests/ -q` (369 passed,
  unchanged), restarted the live server to pick up the change and
  confirmed live against real HTTP: no-`expand` request keeps
  `addresses` absent from JSON entirely (matches pre-existing evidence-
  backed default), `expand=all` populates real `Address`/
  `BusinessPartnerBank` content, XML round-trips through
  `ElementTree.parse` without error. Note: the delegation prompt
  incorrectly referenced "18 known pre-existing failures" as a baseline
  to preserve — that number was stale (the referential-integrity epic's
  P3, completed earlier in this same session, had already brought the
  suite to 369/369 green); the implementer correctly caught this
  discrepancy rather than fabricating a reconciliation, flagged it
  instead of guessing. Committed as `bdfb69c` (P1 doc, which had never
  actually been committed after P1 finished) and `144cff7` (P2 code).
- 2026-09-24: P3 complete (delegated direct). Investigated and
  **disconfirmed** the leading "omit vs. null" hypothesis carried over
  from live pre-epic debugging — with real evidence: the real-data-
  reconciliation epic already confirmed "absent, not null" for optional
  fields is genuine real DATEV behavior, not a mock defect; changing it
  would have made the mock less faithful, not more, and the implementer
  correctly declined to make that change despite it being the delegation
  prompt's own leading theory.
  Found the actual root cause instead: two hardcoded date literals
  (`GeneralLedgerAccountTaxRate.valid_from`,
  `PostingProposalRule.creation_date`) had no RFC3339 zone offset
  (`"...000"` vs. every other literal's `"...000+01:00"`) — a Java
  client's `OffsetDateTime.parse()` rejects a naive date-time string,
  and Jersey reports that as exactly ELO's observed generic "Error
  reading entity from input stream." Fixed both literals, plus corrected
  a now-stale `function_description` "unconfirmed" comment (P1 already
  confirmed it's real) — no field-shape/dataclass changes, matching P1's
  verdict that neither resource needed one.
  **Orchestrator extended the fix at its systemic source** after
  reviewing: `_random_timestamp()` itself (used at 13 call sites across
  `app/fake_data.py`, including P2's new `Address`/
  `BusinessPartnerBank.valid_from`) built its result from a naive
  `datetime`, so the same missing-offset defect existed everywhere else
  it's called too — not just the two spots P3 was scoped to. Fixed once
  at the helper (append the same `"+01:00"` convention), re-verified live
  that `Address.valid_from`/`BusinessPartnerBank.valid_from` now carry
  the offset too, re-ran the full suite (369/369, unchanged). Zero test
  files needed updates (confirmed by the delegated agent: no test pins
  an exact date-literal string, only type/presence/enum-membership).
  Committed as `7655c0f`.
- 2026-09-24: **Live re-test surfaced one more real bug**, found and
  fixed before P4 closed: with the RFC3339 date fix live, the user's
  `BusinessPartners` pool (creditors, `expand=all`) still failed with the
  same generic error. Root cause: several `DebitorAccountingInformation`
  enum fields P2 had populated with *invented* placeholder tokens (e.g.
  `"dunning_procedure_option_3"`) — P1's spec research had only recorded
  those fields' member *counts*, not their exact values, and P2 filled
  the gap with placeholders rather than re-querying the spec. A strict
  Java enum deserializer rejects any string that isn't one of the real
  declared constants, exactly like the missing date offset did. Extracted
  the real member lists directly from `datev.debitor-accounting-
  information` in `Accounting-1.5.0.json` (`account_statement`,
  `account_statement_text`, `direct_debit`, `dunning_procedure`,
  `interest_calculation`, `dunning_text1-3`) and replaced every
  placeholder pool. `dunning_period_calculation` was already correct.
  369/369 unchanged. Committed as `ff152d9`, pushed. The user's own
  separate report of a second remaining failure, `cost-centers`, is the
  already-explained real DATEV integer-date spec quirk (root-caused
  before this epic even started) — explicitly not touched, offered the
  user a workaround if they want one, no decision made yet.
- 2026-09-24: P4 done. Added 4 new tests (`test_accounting_partners.py`):
  creditors' `expand=all` populates real content, is deterministic per
  scope, and round-trips correctly through both JSON and XML (the exact
  path P2's `repr()`-string bug would resurface in if it ever regressed);
  a debitors companion that also directly asserts against a real
  `dunning_procedure` enum value and against the RFC3339 offset fix (not
  just "doesn't crash" — asserts the two actual defects found via live
  ELO debugging stay fixed). 369 → 373 passing (caught and fixed one
  test-authoring bug of the orchestrator's own along the way — `record["legal_person"]`
  raised `KeyError` instead of returning `None` on a legitimately-absent
  key; corrected to `.get()`). README updated: 11th epic entry, new
  "Expand and nested content" and "Trusting the mock's TLS certificate
  (Java / enterprise HTTP clients)" Key Decisions subsections (the
  latter a direct how-to write-up of the `keytool -importcert` procedure
  this epic's own live debugging worked out, requested separately by the
  user mid-epic), test badge/count updated. Committed as `510768b`,
  pushed.
  This closes the epic: real `expand=all` nested content for creditors/
  debitors (spec-grounded, not Java-mock-shaped), two genuine bugs found
  via live integration debugging and fixed at their real root cause
  (missing RFC3339 zone offsets — fixed systemically at
  `_random_timestamp()`'s source, not just the two originally-reported
  spots — and invented-vs-real enum values), 373/373 tests green,
  committed across 4 phases plus 2 live-debugging follow-up fixes, all
  pushed to `main`. One confirmed-real, deliberately-untouched item
  remains open for the user's own call: `cost-centers`' integer-encoded
  dates are correct per DATEV's real spec and not something this mock
  should change to accommodate one client's gap.

## Appendix — official spec field tables (P1)

Source: `C:\Mockup\main\mockdata\apispec\Accounting-1.5.0.json`, extracted
fresh this phase (`"C:\ELO\java\bin\jar.exe" xf serve-0.1-generate.jar
"main/mockdata/apispec/Accounting-1.5.0.json"`, OpenAPI 3.0.1, 68 schemas
under `components.schemas`). Resolved with a one-off script that walks
each named schema's `properties`, records `type`/`format`/`enum`, follows
`$ref` to the referenced schema name (one level — nested `$ref`s are
resolved separately below), and reads the schema's own `required` array.
Format: `field_name (type, required|optional)` — same convention as
`datev-mock-write-endpoints-and-observability.md`'s Appendix A. **Every
schema in this spec family has an empty top-level `required: []`** except
`datev.address` (`address_usage_type` required) — DATEV's own contract
treats almost everything as independently omittable, matching this
project's existing "everything `Optional`" dataclass convention.

### Creditor / Debitor top-level (`creditor` / `debitor`)

Both schemas are structurally identical (same field names, same order in
the spec file): `id` (str), `account_number` (int), `accounting_information`
(→ `datev.creditor-accounting-information` / `datev.debitor-accounting-
information`), `addressee_id` (str), `alternative_search_name` (str),
`business_partner_number` (str), `business_partner_relation_id` (str),
`caption` (str, readOnly), `complimentary_close` (str), `correspondence_title`
(str), `date_last_modification` (str date-time, readOnly), `eu_vat_id_country_code`
(str), `eu_vat_id_number` (str), `is_business_partner_active` (bool),
`is_organization_business_partner` (bool), `legal_entity_type` (str, enum
`not_specified`/`natural_person`/`legal_person` — this is what picks which
one of the 3 person sub-objects below is populated), `salutation` (str),
`short_name` (str), `third_party_number` (str), `natural_person` (→
`datev.natural-person`), `legal_person` (→ `datev.legal-person`),
`not_specified_person` (→ `datev.not-specified-person`), `addresses`
(array → `datev.address`), `communications` (array → `datev.communication`),
`banks` (array → `datev.bank`).

**Verdict: top-level shape already matches `app/models.py`'s `Creditor`/
`Debitor` field-for-field** — no new/missing/renamed top-level fields.
The only gap is type: `addresses`/`banks`/`communications` are currently
`Optional[str]` placeholders instead of `Optional[list[...]]` (decision #3).

### `datev.address` (creditor/debitor `addresses[]` item)

`id` (str), `additional_correspondence_title` (str), `additional_delivery_text1`
(str), `additional_delivery_text2` (str), `address_appendix` (str),
`address_manually_edited` (str, readOnly), `address_type` (str, enum
`not_specified`/`street_address`/`post_office_box_address`/
`corporate_client_address`), `address_usage_type` (→ `datev.address-usage-type`,
**REQUIRED** — the only required field anywhere in this schema family),
`city` (str), `country_code` (str), `district` (str),
`individual_shipping_information` (str), `is_address_manually_edited` (bool,
readOnly), `note` (str), `post_office_box` (str), `postal_code` (str),
`street` (str), `valid_from` (str date-time), `valid_to` (str date-time).
18 fields total.

`datev.address-usage-type` (nested, required sub-object of the above — all
7 fields are booleans): `is_correspondence_address`, `is_default_delivery_address`,
`is_default_payment_address`, `is_delivery_address`,
`is_main_post_office_box_address`, `is_main_street_address`,
`is_management_address`.

**No `Address` dataclass exists yet in `app/models.py` — needs creating
from scratch** (decision #3), including the nested `address_usage_type`
sub-object (a new `AddressUsageType` dataclass, or inline booleans — P2's
call).

### `datev.bank` (creditor/debitor `banks[]` item) — **not the same schema as the existing `Bank` dataclass**

`id` (str), `bank_account_number` (str), `bank_code` (str), `bank_name`
(str), `bic` (str), `business_partner_bank_position` (int32),
`country_code` (str), `differing_account_holder` (str), `iban` (str),
`is_business_partner_bank` (bool), `sepa_mandate_reference` (str), `note`
(str), `valid_from` (str date-time), `valid_to` (str date-time). 13 fields.

**Important finding**: `app/models.py` already has a `Bank` dataclass
(line 228, docstring "Master-data `Bank` — full flat schema"), but it's a
*different* schema entirely — `id`, `bank_code`, `bic`, `city`,
`country_code`, `name`, `standard`, `timestamp` (8 fields, from the
Client-Master-Data spec's standalone `banks` master-data endpoint, not
this `Accounting-1.5.0` spec). Only 4 field names overlap (`id`,
`bank_code`, `bic`, `country_code`) and even those mean different things
in context. **Reusing the existing `Bank` class for `Creditor.banks`/
`Debitor.banks` would be wrong** — P2 needs a distinct new dataclass (e.g.
`CreditorBank` or `NestedBank`) matching `datev.bank`'s 13 fields above,
not the master-data `Bank`.

### `datev.communication` (creditor/debitor `communications[]` item)

`id` (str), `communication_data_content` (str), `communication_type` (str,
enum `not_specified`/`phone`/`email`/`url`/`fax`/`other`), `note` (str),
`communication_usage_type` (→ `datev.communication-usage-type`). 5 fields.

`datev.communication-usage-type` (nested sub-object, 2 booleans):
`is_main_communication_usage_type`, `is_main_management_phone`.

**No `Communication` dataclass exists yet — needs creating** (decision
#3), same as `Address`.

### `datev.legal-person` / `datev.natural-person` / `datev.not-specified-person`

- `datev.legal-person`: `enterprise_purpose` (str), `legal_form` (str),
  `legal_name` (str). Matches `LegalPerson` in `app/models.py` field-for-
  field. Note: spec marks `legal_name` optional (not required) — current
  dataclass has it as the sole non-defaulted (required-by-Python) field;
  harmless (this mock always populates it when generating), just not
  spec-mandated.
- `datev.natural-person`: `date_of_birth` (str date-time), `degree` (str),
  `firstname` (str), `name_prefix` (str), `surname` (str),
  `title_of_nobility` (str). Matches `NaturalPerson` field-for-field.
  Same non-required-in-spec note for `firstname`/`surname`.
- `datev.not-specified-person`: `name` (str). Matches `NotSpecifiedPerson`
  exactly. Same note for `name`.

**Verdict: all 3 person sub-objects are already correctly modeled** — zero
new/missing fields, no dataclass changes needed for these three.

### `datev.creditor-accounting-information`

`alternative_contact_person` (str), `clerk` (str), `client_bank_position`
(int32, max 999), `contact_person` (str), `currency_management` (str, enum
`payments_in_input_currency`/`payments_in_euro`), `is_insolvent` (bool),
`is_various_account` (bool), `language` (str, enum `not_specified`/
`german`/`french`/`english`/`spanish`/`italian`), `output_destination`
(str, enum `not_specified`/`print`/`fax`/`email`), `payment_medium` (str,
enum `not_specified`/`individual_check`/`collective_check`/
`sepa_bank_transfer_with_one_invoice`/`sepa_bank_transfer_with_multiple_invoices`/
`no_bank_transfer`), `tax_number` (str), `temp_payment_block` (str
date-time), `term_of_payment_id` (int32), `individual_fields` (array →
`datev.individual-field`: `content` str, `position` int32 — max 10 items).
14 fields.

**Diff vs `CreditorAccountingInformation`** (currently 7 fields:
`currency_management`, `is_insolvent`, `is_various_account`, `language`,
`output_destination`, `payment_medium`, `term_of_payment_id`) — **missing
7 spec fields**: `alternative_contact_person`, `clerk`,
`client_bank_position`, `contact_person`, `tax_number`,
`temp_payment_block`, `individual_fields`. No invented/extra fields on the
current dataclass — everything it has is real, just incomplete.

### `datev.debitor-accounting-information`

`account_statement` (str, enum 5 values), `account_statement_text` (str,
enum 10 values), `alternative_contact_person` (str), `clerk` (str),
`client_bank_position` (int32), `contact_person` (str), `credit_limit`
(int64), `currency_management` (str, enum 2 values), `direct_debit` (str,
enum 4 values), `dunning_final_deadline` (int32, 0-999),
`dunning_interest_rate1`/`2`/`3` (number decimal), `dunning_limit_amount`
(number decimal), `dunning_limit_percent` (number decimal),
`dunning_period1`/`2`/`3` (int32), `dunning_period_calculation` (str, enum
`not_specified`/`calculate_dunning_period`), `dunning_procedure` (str,
enum 7 values), `dunning_text1`/`2`/`3` (→ `datev.dunning-text`, a plain
string enum of 10 text-group values, not an object), `has_enforcement_block`
(bool), `interest_calculation` (str, enum 4 values), `is_insolvent` (bool),
`is_various_account` (bool), `language` (str, enum 6 values),
`output_destination` (str, enum 4 values), `tax_number` (str),
`temp_direct_debit_block` (str date-time), `temp_enforcement_block` (str
date-time), `temp_dunning_block` (str date-time), `term_of_payment_id`
(int32), `individual_fields` (array → `datev.individual-field`). 32 fields.

**Diff vs `DebitorAccountingInformation`** (currently 11 fields:
`account_statement`, `credit_limit`, `currency_management`,
`direct_debit`, `dunning_procedure`, `interest_calculation`,
`is_insolvent`, `is_various_account`, `language`, `output_destination`,
`term_of_payment_id`) — **missing 21 spec fields**: `account_statement_text`,
`alternative_contact_person`, `clerk`, `client_bank_position`,
`contact_person`, `dunning_final_deadline`, `dunning_interest_rate1/2/3`,
`dunning_limit_amount`, `dunning_limit_percent`, `dunning_period1/2/3`,
`dunning_period_calculation`, `dunning_text1/2/3`, `has_enforcement_block`,
`tax_number`, `temp_direct_debit_block`, `temp_enforcement_block`,
`temp_dunning_block`, `individual_fields`. Same pattern as the creditor
side — nothing invented, just a much larger real gap (DATEV's debitor
accounting-information contract is genuinely richer than creditor's).
**P2/P3 note**: neither architecture decision #2 nor #3 requires closing
these two gaps completely to satisfy ELO's actual request (ELO only asked
for `accounting_information` to exist and be populated, not for every
spec field) — P2 can choose to keep the current 7/11-field subset
populated under `expand=all` and treat full parity as optional/future
scope, or expand both dataclasses now; either is spec-grounded, this is a
scope call for P2, not a P1 finding to resolve.

### `general-ledger-account` / `datev.general-ledger-account-tax-rates`

`general-ledger-account`: `id` (str), `account_number` (int32),
`additional_function` (int32), `caption` (str), `function_description`
(str), `function_extension` (int32), `main_function` (int32),
`main_function_number` (int32), `tax_rates` (array →
`datev.general-ledger-account-tax-rates`). 9 fields.

`datev.general-ledger-account-tax-rates`: `tax_rate` (number decimal),
`valid_from` (str date-time), `valid_to` (str date-time). 3 fields.

**Verdict: `GeneralLedgerAccount`/`GeneralLedgerAccountTaxRate` already
match the spec field-for-field**, including `function_description` (which
`app/models.py`'s own comment flagged as "extra, unconfirmed" — the spec
**confirms it's real**, not invented) and `tax_rates` (confirmed to exist,
with the exact same 3-field item shape already modeled). **No field-shape
changes needed for P3 on this resource** — ELO's `select=...,tax_rates`
failure is not a wrong-shape problem, it's that `tax_rates` presumably
isn't being populated/serialized correctly yet (worth P3/P4 checking the
actual generator + JSON/XML output, but the *dataclass* shape itself is
already spec-correct).

### `posting-proposal-rule-incoming-invoices` / `-outgoing-invoices`

Both schemas, identical top-level shape: `id` (str), `assignment_criteria`
(→ `datev.assignment-criteria-invoices`), `creation_date` (str date-time),
`last_used_date` (str date-time), `posting_proposal_information` (array →
`datev.posting-proposal-information-incoming-invoices` /
`-outgoing-invoices` respectively), `uncertain_label` (bool). 6 fields.

`datev.assignment-criteria-invoices`: `goods_and_services` (str), `name`
(str), `tax_rate` (number decimal). 3 fields.

`datev.posting-proposal-information-incoming-invoices`:
`accounting_transaction_key` (int32), `account_number` (int32),
`business_partner_account_number` (int32), `kost1_cost_center_id` (str),
`kost2_cost_center_id` (str), `posting_description` (str),
`origin_of_posting_description` (str, enum `own_input`/
`posting_description`/`goods_and_services`/`business_partner_name`/
`not_specified` — 5 values). 7 fields.

`datev.posting-proposal-information-outgoing-invoices`: identical 7
fields; only difference is `origin_of_posting_description`'s enum has 2
extra values (`email`, `transaction_key` — 7 values total).

**Verdict: `PostingProposalRule`/`AssignmentCriteria`/
`PostingProposalInformation` already match the spec field-for-field**,
including the "outgoing has two extra enum values" claim already in the
`PostingProposalInformation` docstring (**confirmed exactly**: `email` and
`transaction_key`). This directly resolves the epic's original root-cause
uncertainty (section "Root cause", `general-ledger-accounts`/
`posting-proposal-rules-*` bullet) — the field set this project invented
by pattern turns out to already be a correct match to the *official*
spec; the Java reference mock's differing behavior (different apparent
field set, e.g. `kost1_cost_center_id` visible there) is explained by our
dataclass already including that same field (just possibly nil/
unpopulated in typical fake-data output) rather than a real shape gap.
**No field-shape changes needed for P3 on this resource either** — same
caveat as GL-accounts: worth P3/P4 checking that `assignment_criteria`/
`posting_proposal_information` are actually being generated/serialized
under `select=...`, since the dataclass shape itself needs no correction.

### `datev.cost-rate` — `CostRate` integer-date claim: **CONFIRMED**

Exact spec entry:

```json
"datev.cost-rate": {
  "type": "object",
  "properties": {
    "valid_from": { "type": "integer", "example": 20161201,
      "description": "(Gültig von) Valid from, only available in the
      product specifications of Kostenrechnung classic" },
    "valid_to": { "type": "integer", "example": 20161231,
      "description": "(Gültig bis) Valid to, only available in the
      product specifications of Kostenrechnung classic" },
    "rate": { "type": "number", "maximum": 9999999.99, "example": 1234567.12,
      "description": "(Kostensatz) Cost rate, only available in the
      product specifications of Kostenrechnung classic" }
  }
}
```

`valid_from`/`valid_to` are typed `integer` (not `string`/`date`), with
examples `20161201`/`20161231` — unambiguously YYYYMMDD integer-encoded
dates, exactly as `CostRate`'s docstring already claims. **Verdict:
confirmed, docstring is accurate — no `app/models.py` edit made this
phase.** `CostCenter`'s other 12 top-level fields also match `cost-center`
1:1 by name (not part of this task's required checks, noted in passing).

### Summary — what's new vs. what `app/models.py` already has (P2/P3 checklist)

| Resource | Verdict | Action for P2/P3 |
|---|---|---|
| `Creditor`/`Debitor` top-level | Matches spec exactly | none |
| `Creditor.addresses`/`Debitor.addresses` | No `Address` dataclass exists | Create `Address` (18 fields) + nested `AddressUsageType`/booleans (decision #3) |
| `Creditor.banks`/`Debitor.banks` | No matching dataclass — existing `Bank` is a **different** schema | Create a new nested-bank dataclass (13 fields, `datev.bank`); do not reuse master-data `Bank` |
| `Creditor.communications`/`Debitor.communications` | No `Communication` dataclass exists | Create `Communication` (5 fields) + `CommunicationUsageType` (2 bools) |
| `legal_person`/`natural_person`/`not_specified_person` | Already correct | none |
| `CreditorAccountingInformation` | 7/14 spec fields modeled | Add 7 missing fields, or explicitly scope-limit (P2 call) |
| `DebitorAccountingInformation` | 11/32 spec fields modeled | Add up to 21 missing fields, or explicitly scope-limit (P2 call) |
| `GeneralLedgerAccount`/`GeneralLedgerAccountTaxRate` | Matches spec exactly | none — check generation/serialization instead |
| `PostingProposalRule`/`AssignmentCriteria`/`PostingProposalInformation` | Matches spec exactly | none — check generation/serialization instead |
| `CostRate` | Docstring confirmed accurate | none |

### Ambiguities / not fully resolved

- Whether P2 should close the `CreditorAccountingInformation`/
  `DebitorAccountingInformation` field gaps fully or keep the current
  narrower subset is a scope decision, not a spec-reading ambiguity — the
  spec itself is unambiguous on all fields checked above.
- This phase did not investigate *why* `tax_rates`/`assignment_criteria`/
  `posting_proposal_information` currently fail to satisfy ELO despite
  correct dataclass shapes (P1 was explicitly scoped to field-shape
  research only, `app/` untouched) — flagged above for P3/P4 to check the
  actual generator and `select=`/serialization code path, since the root
  cause there is evidently not a shape mismatch.
- `cost-center.properties[]` items (`datev.cost-center-property`: `id`,
  `characteristic_id`) are currently modeled as generic `list[dict]`, not
  a typed dataclass — out of this task's required scope (only `cost_rates`
  was asked for), noted only in passing, not part of the checklist above.

## Post-epic follow-ups (2026-09-24, same day, after the epic's own close)

Real live ELO retesting surfaced two more issues after P4 closed. Both
handled directly (small, well-understood, no new phase needed):

1. **`BusinessPartners` (creditors) still failed after P3/P4.** Root
   cause: `Creditor`/`Debitor.natural_person.date_of_birth` (P2's own new
   code) was truncated to `[:10]` (date-only), but
   `datev.natural-person.date_of_birth` is spec-typed `date-time` — same
   RFC3339-offset bug class as P3's fix, just in a field only reachable
   once `expand=all` actually returns nested content, so nothing earlier
   could have caught it live. Fixed at both generation sites. Verified
   against the *exact* client/fiscal-year scope and query string ELO's
   own log showed still failing. Committed `64e4f9b`.
2. **`start.bat` reported as "just closes."** Reproduced directly: a
   leftover mock instance (from this session's own testing) was already
   holding port 58452; the resulting uvicorn bind-error traceback flashed
   by in a double-clicked window with nothing to read it before the
   window closed. Both launchers now check the port before binding and
   print a clear "already running" message (`start.bat`'s check uses a
   PowerShell `TcpClient` probe, not `netstat` text parsing — that output
   is locale-dependent, e.g. German Windows reports `"ABHÖREN"` not
   `"LISTENING"`, so a text-matching check silently never fired on this
   very machine); `start.bat` also now pauses on any abnormal uvicorn
   exit so the window never vanishes without showing why. Committed
   `f67c4e0`.
3. **User-requested follow-on feature**: a persisted `datev_api_version`
   setting (`"legacy"`/`"modern"`, default `"legacy"`), same mechanism as
   `default_accounting_format` (`settings.json`, admin UI, `PUT
   /admin/api/settings`, no restart needed) — `cost-centers` omits
   `cost_rates` entirely in `"legacy"` mode (matching ELO's older
   reference mock's shape, the actual confirmed-real DATEV spec quirk
   from decision #1/the Root Cause section stays exactly as documented,
   this only controls whether it's *exposed*) versus the full
   spec-accurate shape in `"modern"` mode. New tests for both values plus
   the admin API round-trip; 375/375. Committed `90c2cb6`.

All pushed to `main`.
