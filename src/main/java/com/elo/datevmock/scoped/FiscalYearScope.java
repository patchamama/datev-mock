package com.elo.datevmock.scoped;

import com.elo.datevmock.model.CostSystem;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.TermOfPayment;

import java.util.List;

/**
 * One {@code (clientId, fiscalYearId)} scope's cached bundle — ports
 * {@code app/scoped_data.py::_FiscalYearScope}, trimmed to the resource
 * families SB3 actually needs to prove the scoping/caching/cross-reference
 * mechanism (cost systems, terms of payment, creditors). The remaining
 * resource families in the Python original (debitors, general-ledger
 * accounts, accounting sequences/transaction keys, open items, asset
 * stocktakings, posting-proposal rules) get added here domain-by-domain as
 * SB5-SB8 port their owning HTTP endpoints — this record grows, callers of
 * {@link ScopedDataService} don't change shape.
 */
record FiscalYearScope(
        List<CostSystem> costSystems,
        List<TermOfPayment> termsOfPayment,
        List<Creditor> creditors
) {
}
