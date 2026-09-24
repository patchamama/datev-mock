package com.elo.datevmock.scoped;

import com.elo.datevmock.model.AccountingSequenceProcessed;
import com.elo.datevmock.model.AccountingTransactionKey;
import com.elo.datevmock.model.AssetStocktaking;
import com.elo.datevmock.model.CostSystem;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.Debitor;
import com.elo.datevmock.model.GeneralLedgerAccount;
import com.elo.datevmock.model.OpenItem;
import com.elo.datevmock.model.PostingProposalRule;
import com.elo.datevmock.model.TermOfPayment;

import java.util.List;

/**
 * One {@code (clientId, fiscalYearId)} scope's cached bundle — ports
 * {@code app/scoped_data.py::_FiscalYearScope}. SB6 (accounting read API
 * parity) filled in every resource family beyond SB3's original cost
 * systems/terms of payment/creditors trio.
 */
record FiscalYearScope(
        List<CostSystem> costSystems,
        List<TermOfPayment> termsOfPayment,
        List<Creditor> creditors,
        List<Debitor> debitors,
        List<GeneralLedgerAccount> generalLedgerAccounts,
        List<AccountingSequenceProcessed> accountingSequencesProcessed,
        List<AccountingTransactionKey> accountingTransactionKeys,
        List<OpenItem> accountsPayable,
        List<OpenItem> accountsPayableCondense,
        List<OpenItem> accountsReceivableCondense,
        List<AssetStocktaking> assetsStocktakings,
        List<PostingProposalRule> postingProposalRulesIncomingInvoices,
        List<PostingProposalRule> postingProposalRulesOutgoingInvoices
) {
}
