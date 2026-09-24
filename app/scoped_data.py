"""Deterministic per-scope fake-data generation and caching for the
accounting sub-resources nested under `/clients/{client_id}/fiscal-years/
{fiscal_year_id}[/cost-systems/{cost_system_id}]/...`.

Implements architecture decisions #1-#4 of
`odd/tasks/datev-mock-referential-integrity.md`: for any `client_id` (and,
nested, any `fiscal_year_id`, and, nested further, any `cost_system_id`),
this module generates a fresh, internally-consistent dataset the *first
time* that exact scope key is used, then caches it in memory for the
process lifetime — no scope key is ever rejected as "unknown" (decision
#1's lenient-deterministic design), and no eviction/reset is needed between
tests (decision #3): generation is deterministic per scope key via
`_seed_for`, not per-process random state.

Master-data (`Client`/`Addressee`/`Bank`/`Employee`) and DMS (`Domain`/
`Document`) stay global/unscoped, generated once at `app.fake_data` import
time exactly as before — this module only adds scoping for the accounting
sub-resources nested under a client/fiscal-year path. The one exception,
per decision #4, is `Creditor`/`Debitor.addressee_id`, which deliberately
reaches into the **global** `Addressee.id` list (master data isn't scoped,
so addressees are genuinely client-independent in this mock's modeling).

Per-record field-shape logic (name pools, address/date generation, etc.)
lives in `app/fake_data.py`'s existing `_generate_*` functions, which this
module calls with a scope-dedicated `random.Random` instance and (where
architecture decision #4 calls for a real cross-reference) the target
scope's own already-generated id/record lists — see each `_generate_*`
function's own docstring in `app/fake_data.py` for exactly what changed.

Design call not fully spelled out by the task doc: `cost_systems`/
`general_ledger_accounts`/`terms_of_payment`/`accounting_sequences_processed`/
`accounting_transaction_keys` had no built-in randomness in their original
`app/fake_data.py` generators and decision #4 lists no cross-reference
*into* them from elsewhere. To keep the change surface minimal/low-risk for
existing unscoped/global call sites (module-import-time dataset generation,
`app/data_store.py::reset()`), each of these generators now takes an
optional `rng` guarded by `if rng is not None: ...` — when omitted (every
pre-existing call site), the original fixed index-derived values are
produced byte-for-byte unchanged (zero shift to the shared `random`
module's global draw sequence); when this module passes a scope-dedicated
`random.Random` instance, real per-scope variation is produced instead.
`id`/`number`/`account_number` fields that other resources cross-reference
by id (architecture decision #4) stay index-derived on purpose — the
*values* referenced are always drawn from the scope's own real generated
record either way, so varying the id itself isn't required for
correctness, only for keeping ids short and predictable.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from app import fake_data
from app.data_store import list_addressees
from app.models import (
    AccountingSequenceProcessed,
    AccountingTransactionKey,
    AssetStocktaking,
    CostCenter,
    CostSystem,
    Creditor,
    Debitor,
    FiscalYear,
    GeneralLedgerAccount,
    OpenItem,
    PostingProposalRule,
    TermOfPayment,
)


def _seed_for(*parts: str) -> int:
    """Stable SHA256-based seed for a scope key — stable across processes,
    unlike Python's salted `hash()` (architecture decision #2)."""
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:16], 16)


@dataclass
class _FiscalYearScope:
    """One `(client_id, fiscal_year_id)` scope's cached bundle — every
    resource nested one level below a fiscal year (architecture decision
    #2's scope list)."""

    cost_systems: list[CostSystem]
    terms_of_payment: list[TermOfPayment]
    creditors: list[Creditor]
    debitors: list[Debitor]
    general_ledger_accounts: list[GeneralLedgerAccount]
    accounting_sequences_processed: list[AccountingSequenceProcessed]
    accounting_transaction_keys: list[AccountingTransactionKey]
    accounts_payable: list[OpenItem]
    accounts_payable_condense: list[OpenItem]
    accounts_receivable_condense: list[OpenItem]
    assets_stocktakings: list[AssetStocktaking]
    posting_proposal_rules_incoming_invoices: list[PostingProposalRule]
    posting_proposal_rules_outgoing_invoices: list[PostingProposalRule]


# --- scope caches (architecture decision #3): lazily populated, no eviction,
# no reset needed between tests/requests — a scope key's data is stable for
# the process lifetime once first generated.

_fiscal_years_cache: dict[tuple[str], list[FiscalYear]] = {}
_fiscal_year_scope_cache: dict[tuple[str, str], _FiscalYearScope] = {}
_cost_centers_cache: dict[tuple[str, str, str], list[CostCenter]] = {}


def _get_cost_centers(client_id: str, fiscal_year_id: str, cost_system_id: str) -> list[CostCenter]:
    key = (client_id, fiscal_year_id, cost_system_id)
    cached = _cost_centers_cache.get(key)
    if cached is not None:
        return cached
    rng = random.Random(_seed_for(client_id, fiscal_year_id, cost_system_id))
    records = fake_data._generate_cost_centers(rng=rng)
    _cost_centers_cache[key] = records
    return records


def _get_fiscal_year_scope(client_id: str, fiscal_year_id: str) -> _FiscalYearScope:
    key = (client_id, fiscal_year_id)
    cached = _fiscal_year_scope_cache.get(key)
    if cached is not None:
        return cached

    rng = random.Random(_seed_for(client_id, fiscal_year_id))
    addressee_ids = [record.id for record in list_addressees()]

    cost_systems = fake_data._generate_cost_systems(rng=rng)
    terms_of_payment = fake_data._generate_terms_of_payment(rng=rng)
    general_ledger_accounts = fake_data._generate_general_ledger_accounts(rng=rng)
    accounting_sequences_processed = fake_data._generate_accounting_sequences_processed(rng=rng)
    accounting_transaction_keys = fake_data._generate_accounting_transaction_keys(rng=rng)

    creditors = fake_data._generate_creditors(rng=rng, addressee_ids=addressee_ids)
    debitors = fake_data._generate_debitors(rng=rng, addressee_ids=addressee_ids)

    # OpenItem.kost1_cost_center_id references the fiscal year's *primary*
    # cost system — deterministically index 0 of this scope's generated
    # cost systems (architecture decision #4; OpenItem has no
    # cost_system_id of its own in its path, so it needs one fixed cost
    # system to cross-reference). GET .../cost-systems/{cost_system_id}/
    # cost-centers still correctly serves *any* cost_system_id independent
    # of which one is "primary" here (see get_cost_centers_for_scope).
    primary_cost_system_id = cost_systems[0].id
    primary_cost_centers = _get_cost_centers(client_id, fiscal_year_id, primary_cost_system_id)

    term_of_payment_ids = [int(record.id) for record in terms_of_payment]
    accounting_sequence_ids = [record.id for record in accounting_sequences_processed]
    cost_center_ids = [record.id for record in primary_cost_centers]

    accounts_payable = fake_data._generate_open_items(
        receivable=False,
        rng=rng,
        term_of_payment_ids=term_of_payment_ids,
        accounting_sequence_ids=accounting_sequence_ids,
        cost_center_ids=cost_center_ids,
    )
    accounts_payable_condense = fake_data._generate_open_items(
        receivable=False,
        rng=rng,
        term_of_payment_ids=term_of_payment_ids,
        accounting_sequence_ids=accounting_sequence_ids,
        cost_center_ids=cost_center_ids,
    )
    accounts_receivable_condense = fake_data._generate_open_items(
        receivable=True,
        rng=rng,
        term_of_payment_ids=term_of_payment_ids,
        accounting_sequence_ids=accounting_sequence_ids,
        cost_center_ids=cost_center_ids,
    )

    assets_stocktakings = fake_data._generate_asset_stocktakings(
        rng=rng, general_ledger_accounts=general_ledger_accounts
    )

    posting_proposal_rules_incoming_invoices = fake_data._generate_posting_proposal_rules(
        outgoing=False,
        rng=rng,
        accounting_transaction_keys=accounting_transaction_keys,
        general_ledger_accounts=general_ledger_accounts,
    )
    posting_proposal_rules_outgoing_invoices = fake_data._generate_posting_proposal_rules(
        outgoing=True,
        rng=rng,
        accounting_transaction_keys=accounting_transaction_keys,
        general_ledger_accounts=general_ledger_accounts,
    )

    scope = _FiscalYearScope(
        cost_systems=cost_systems,
        terms_of_payment=terms_of_payment,
        creditors=creditors,
        debitors=debitors,
        general_ledger_accounts=general_ledger_accounts,
        accounting_sequences_processed=accounting_sequences_processed,
        accounting_transaction_keys=accounting_transaction_keys,
        accounts_payable=accounts_payable,
        accounts_payable_condense=accounts_payable_condense,
        accounts_receivable_condense=accounts_receivable_condense,
        assets_stocktakings=assets_stocktakings,
        posting_proposal_rules_incoming_invoices=posting_proposal_rules_incoming_invoices,
        posting_proposal_rules_outgoing_invoices=posting_proposal_rules_outgoing_invoices,
    )
    _fiscal_year_scope_cache[key] = scope
    return scope


# --- public accessors — the accounting router's API surface (P1 step 2) ---


def get_fiscal_years_for_client(client_id: str) -> list[FiscalYear]:
    key = (client_id,)
    cached = _fiscal_years_cache.get(key)
    if cached is not None:
        return cached

    rng = random.Random(_seed_for(client_id))
    base_year = 2018 + rng.randint(0, 6)
    records = fake_data._generate_fiscal_years(base_year=base_year)

    # Architecture decision #4: creditor_term_of_payment_id/
    # debitor_term_of_payment_id are backfilled from *that specific fiscal
    # year's own* generated term-of-payment scope — generate the fiscal
    # year's id first (above), then its nested term-of-payment scope (via
    # _get_fiscal_year_scope), then backfill these two fields.
    for record in records:
        scope = _get_fiscal_year_scope(client_id, record.id)
        term_of_payment_ids = [int(item.id) for item in scope.terms_of_payment]
        if term_of_payment_ids:
            record.creditor_term_of_payment_id = rng.choice(term_of_payment_ids)
            if record.debitor_term_of_payment_id is not None:
                record.debitor_term_of_payment_id = rng.choice(term_of_payment_ids)

    _fiscal_years_cache[key] = records
    return records


def get_cost_systems_for_scope(client_id: str, fiscal_year_id: str) -> list[CostSystem]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).cost_systems


def get_cost_centers_for_scope(
    client_id: str, fiscal_year_id: str, cost_system_id: str
) -> list[CostCenter]:
    return _get_cost_centers(client_id, fiscal_year_id, cost_system_id)


def get_creditors_for_scope(client_id: str, fiscal_year_id: str) -> list[Creditor]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).creditors


def get_debitors_for_scope(client_id: str, fiscal_year_id: str) -> list[Debitor]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).debitors


def get_general_ledger_accounts_for_scope(
    client_id: str, fiscal_year_id: str
) -> list[GeneralLedgerAccount]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).general_ledger_accounts


def get_terms_of_payment_for_scope(client_id: str, fiscal_year_id: str) -> list[TermOfPayment]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).terms_of_payment


def get_accounting_sequences_processed_for_scope(
    client_id: str, fiscal_year_id: str
) -> list[AccountingSequenceProcessed]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).accounting_sequences_processed


def get_accounting_transaction_keys_for_scope(
    client_id: str, fiscal_year_id: str
) -> list[AccountingTransactionKey]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).accounting_transaction_keys


def get_accounts_payable_for_scope(client_id: str, fiscal_year_id: str) -> list[OpenItem]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).accounts_payable


def get_accounts_payable_condense_for_scope(client_id: str, fiscal_year_id: str) -> list[OpenItem]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).accounts_payable_condense


def get_accounts_receivable_condense_for_scope(client_id: str, fiscal_year_id: str) -> list[OpenItem]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).accounts_receivable_condense


def get_assets_stocktakings_for_scope(client_id: str, fiscal_year_id: str) -> list[AssetStocktaking]:
    return _get_fiscal_year_scope(client_id, fiscal_year_id).assets_stocktakings


def get_posting_proposal_rules_incoming_invoices_for_scope(
    client_id: str, fiscal_year_id: str
) -> list[PostingProposalRule]:
    return _get_fiscal_year_scope(
        client_id, fiscal_year_id
    ).posting_proposal_rules_incoming_invoices


def get_posting_proposal_rules_outgoing_invoices_for_scope(
    client_id: str, fiscal_year_id: str
) -> list[PostingProposalRule]:
    return _get_fiscal_year_scope(
        client_id, fiscal_year_id
    ).posting_proposal_rules_outgoing_invoices
