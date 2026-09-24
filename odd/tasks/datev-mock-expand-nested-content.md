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

- [ ] P1 — Research: fresh official-spec extraction and field-shape
      resolution for all 3 endpoint families (decision #1). Durable
      output: an Appendix in this doc (same convention as this project's
      other epics), not just an agent's transient report.
- [ ] P2 — `creditors`/`debitors` `expand=all`: new/promoted dataclasses
      (`Address`, `Communication`, promoted `addresses`/`banks`/
      `communications` types), scoped-deterministic generation, query-
      param-aware router logic, working XML + JSON rendering.
- [ ] P3 — `general-ledger-accounts`/`posting-proposal-rules-*` field-
      shape correction per P1's findings.
- [ ] P4 — Test suite updates (new `expand=all` coverage; updated shape
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
