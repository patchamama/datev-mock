package com.elo.datevmock.scoped;

import com.elo.datevmock.model.AccountingSequenceProcessed;
import com.elo.datevmock.model.AccountingTransactionKey;
import com.elo.datevmock.model.AssetStocktaking;
import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.model.CostRate;
import com.elo.datevmock.model.CostSystem;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.Debitor;
import com.elo.datevmock.model.FiscalYear;
import com.elo.datevmock.model.GeneralLedgerAccount;
import com.elo.datevmock.model.OpenItem;
import com.elo.datevmock.model.PostingProposalRule;
import com.elo.datevmock.model.TermOfPayment;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/**
 * Ports {@code app/scoped_data.py}: deterministic, per-scope fake-data
 * generation and caching for accounting sub-resources nested under a
 * client/fiscal-year (and, for cost centers, cost-system) path.
 *
 * <p>Same design as the FastAPI original: no scope key is ever rejected as
 * "unknown" (lenient-deterministic), generation happens lazily on first use
 * and is cached for the process lifetime (no eviction/reset here — SB4
 * owns reset semantics for SQLite-backed overlays; this in-memory
 * generation cache is a different, simpler layer that FastAPI's own reset
 * doesn't touch either), and a scope's data is a pure function of its scope
 * key via SHA256-seeded {@link ScopeSeed} rather than process-wide random
 * state.
 *
 * <p><b>Generated field values are not byte-identical to the Python
 * original</b> and that is not a goal: {@link Random} and CPython's
 * Mersenne Twister are different PRNGs that don't accept comparable seeds.
 * What is ported faithfully is the <i>architecture</i> — same scope key
 * always returns the same cached instance; distinct scope keys are cached
 * (and seeded) independently; cross-referenced ids (a creditor's
 * {@code addresseeId}, a fiscal year's {@code creditorTermOfPaymentId})
 * always point at a real record from the correct scope.
 *
 * <p>SB6 filled in every resource family {@code _get_fiscal_year_scope}
 * generates in the Python original: debitors, general-ledger accounts,
 * accounting sequences/transaction keys, open items (payable/condense),
 * asset stocktakings, and posting-proposal rules (incoming/outgoing).
 */
@Component
public class ScopedDataService {

    private static final List<String> PERSON_NAME_POOL = List.of(
            "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker");

    private static final int FISCAL_YEARS_PER_CLIENT = 3;
    private static final int COST_SYSTEMS_PER_SCOPE = 3;
    private static final int TERMS_OF_PAYMENT_PER_SCOPE = 4;
    private static final int CREDITORS_PER_SCOPE = 4;
    private static final int DEBITORS_PER_SCOPE = 4;
    private static final int COST_CENTERS_PER_SCOPE = 4;
    private static final int GL_ACCOUNTS_PER_SCOPE = 5;
    private static final int ACCOUNTING_SEQUENCES_PER_SCOPE = 3;
    private static final int TRANSACTION_KEYS_PER_SCOPE = 3;
    private static final int OPEN_ITEMS_PER_SCOPE = 3;
    private static final int ASSET_STOCKTAKINGS_PER_SCOPE = 2;
    private static final int PROPOSAL_RULES_PER_SCOPE = 2;

    private final ConcurrentMap<String, List<FiscalYear>> fiscalYearsCache = new ConcurrentHashMap<>();
    private final ConcurrentMap<FiscalYearScopeKey, FiscalYearScope> fiscalYearScopeCache = new ConcurrentHashMap<>();
    private final ConcurrentMap<CostCenterScopeKey, List<CostCenter>> costCentersCache = new ConcurrentHashMap<>();

    // --- public accessors -------------------------------------------------

    public List<FiscalYear> getFiscalYearsForClient(String clientId) {
        return fiscalYearsCache.computeIfAbsent(clientId, this::generateFiscalYears);
    }

    public List<CostSystem> getCostSystemsForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).costSystems();
    }

    public List<CostCenter> getCostCentersForScope(String clientId, String fiscalYearId, String costSystemId) {
        CostCenterScopeKey key = new CostCenterScopeKey(clientId, fiscalYearId, costSystemId);
        return costCentersCache.computeIfAbsent(key, k -> {
            Random rng = new Random(ScopeSeed.seedFor(clientId, fiscalYearId, costSystemId));
            return generateCostCenters(rng);
        });
    }

    public List<TermOfPayment> getTermsOfPaymentForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).termsOfPayment();
    }

    public List<Creditor> getCreditorsForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).creditors();
    }

    public List<Debitor> getDebitorsForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).debitors();
    }

    public List<GeneralLedgerAccount> getGeneralLedgerAccountsForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).generalLedgerAccounts();
    }

    public List<AccountingSequenceProcessed> getAccountingSequencesProcessedForScope(
            String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).accountingSequencesProcessed();
    }

    public List<AccountingTransactionKey> getAccountingTransactionKeysForScope(
            String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).accountingTransactionKeys();
    }

    public List<OpenItem> getAccountsPayableForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).accountsPayable();
    }

    public List<OpenItem> getAccountsPayableCondenseForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).accountsPayableCondense();
    }

    public List<OpenItem> getAccountsReceivableCondenseForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).accountsReceivableCondense();
    }

    public List<AssetStocktaking> getAssetsStocktakingsForScope(String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).assetsStocktakings();
    }

    public List<PostingProposalRule> getPostingProposalRulesIncomingInvoicesForScope(
            String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).postingProposalRulesIncomingInvoices();
    }

    public List<PostingProposalRule> getPostingProposalRulesOutgoingInvoicesForScope(
            String clientId, String fiscalYearId) {
        return getFiscalYearScope(clientId, fiscalYearId).postingProposalRulesOutgoingInvoices();
    }

    // --- fiscal-year scope --------------------------------------------------

    private FiscalYearScope getFiscalYearScope(String clientId, String fiscalYearId) {
        FiscalYearScopeKey key = new FiscalYearScopeKey(clientId, fiscalYearId);
        return fiscalYearScopeCache.computeIfAbsent(key, k -> buildFiscalYearScope(clientId, fiscalYearId));
    }

    private FiscalYearScope buildFiscalYearScope(String clientId, String fiscalYearId) {
        Random rng = new Random(ScopeSeed.seedFor(clientId, fiscalYearId));

        List<CostSystem> costSystems = generateCostSystems(rng);
        List<TermOfPayment> termsOfPayment = generateTermsOfPayment(rng);
        List<Creditor> creditors = generateCreditors(rng, GlobalAddresseePool.ADDRESSEE_IDS);
        List<Debitor> debitors = generateDebitors(rng, GlobalAddresseePool.ADDRESSEE_IDS);
        List<GeneralLedgerAccount> generalLedgerAccounts = generateGeneralLedgerAccounts(rng);
        List<AccountingSequenceProcessed> accountingSequencesProcessed = generateAccountingSequencesProcessed(rng);
        List<AccountingTransactionKey> accountingTransactionKeys = generateAccountingTransactionKeys(rng);

        // Primary cost system (architecture decision #4, ported from
        // `_get_fiscal_year_scope`): index 0 of this scope's own cost
        // systems, cached the normal way through the public accessor so
        // `getCostCentersForScope` and this internal lookup always agree.
        String primaryCostSystemId = costSystems.get(0).id();
        List<CostCenter> primaryCostCenters = getCostCentersForScope(clientId, fiscalYearId, primaryCostSystemId);

        List<String> termOfPaymentIds = termsOfPayment.stream().map(TermOfPayment::id).toList();
        List<String> accountingSequenceIds = accountingSequencesProcessed.stream()
                .map(AccountingSequenceProcessed::id).toList();
        List<String> costCenterIds = primaryCostCenters.stream().map(CostCenter::id).toList();

        List<OpenItem> accountsPayable = generateOpenItems(
                rng, false, termOfPaymentIds, accountingSequenceIds, costCenterIds);
        List<OpenItem> accountsPayableCondense = generateOpenItems(
                rng, false, termOfPaymentIds, accountingSequenceIds, costCenterIds);
        List<OpenItem> accountsReceivableCondense = generateOpenItems(
                rng, true, termOfPaymentIds, accountingSequenceIds, costCenterIds);

        List<AssetStocktaking> assetsStocktakings = generateAssetStocktakings(rng, generalLedgerAccounts);

        List<PostingProposalRule> postingProposalRulesIncoming = generatePostingProposalRules(
                rng, false, accountingTransactionKeys, generalLedgerAccounts);
        List<PostingProposalRule> postingProposalRulesOutgoing = generatePostingProposalRules(
                rng, true, accountingTransactionKeys, generalLedgerAccounts);

        return new FiscalYearScope(
                costSystems,
                termsOfPayment,
                creditors,
                debitors,
                generalLedgerAccounts,
                accountingSequencesProcessed,
                accountingTransactionKeys,
                accountsPayable,
                accountsPayableCondense,
                accountsReceivableCondense,
                assetsStocktakings,
                postingProposalRulesIncoming,
                postingProposalRulesOutgoing
        );
    }

    // --- generation ---------------------------------------------------------

    private List<FiscalYear> generateFiscalYears(String clientId) {
        Random rng = new Random(ScopeSeed.seedFor(clientId));
        int baseYear = 2018 + rng.nextInt(7);

        List<FiscalYear> records = new ArrayList<>();
        for (int index = 0; index < FISCAL_YEARS_PER_CLIENT; index++) {
            int year = baseYear + index;
            String id = year + "0101";

            FiscalYearScope scope = getFiscalYearScope(clientId, id);
            List<String> termOfPaymentIds = scope.termsOfPayment().stream().map(TermOfPayment::id).toList();

            int creditorTermOfPaymentId = 0;
            Integer debitorTermOfPaymentId = null;
            if (!termOfPaymentIds.isEmpty()) {
                creditorTermOfPaymentId = Integer.parseInt(pick(rng, termOfPaymentIds));
                boolean hasDebitorTerm = index == FISCAL_YEARS_PER_CLIENT - 1;
                if (hasDebitorTerm) {
                    debitorTermOfPaymentId = Integer.parseInt(pick(rng, termOfPaymentIds));
                }
            }

            records.add(new FiscalYear(id, creditorTermOfPaymentId, debitorTermOfPaymentId));
        }
        return List.copyOf(records);
    }

    private List<CostSystem> generateCostSystems(Random rng) {
        List<CostSystem> records = new ArrayList<>();
        for (int index = 0; index < COST_SYSTEMS_PER_SCOPE; index++) {
            boolean isActivated = rng.nextDouble() < 0.5;
            records.add(new CostSystem(String.valueOf(index + 1), "KoRe" + (index + 1), isActivated, index + 1, index + 1));
        }
        return List.copyOf(records);
    }

    private List<TermOfPayment> generateTermsOfPayment(Random rng) {
        List<TermOfPayment> records = new ArrayList<>();
        for (int index = 0; index < TERMS_OF_PAYMENT_PER_SCOPE; index++) {
            double discount1 = Math.round((1.0 + rng.nextDouble() * 2.0) * 100.0) / 100.0;
            records.add(new TermOfPayment(
                    String.valueOf(9000 + index),
                    "Zahlungsbedingung " + (index + 1),
                    "due_in_days",
                    discount1,
                    null));
        }
        return List.copyOf(records);
    }

    private List<Creditor> generateCreditors(Random rng, List<String> addresseeIds) {
        List<Creditor> records = new ArrayList<>();
        for (int index = 0; index < CREDITORS_PER_SCOPE; index++) {
            records.add(buildBusinessPartnerAsCreditor(rng, addresseeIds, index, "KRD%03d", 70000));
        }
        return List.copyOf(records);
    }

    private List<Debitor> generateDebitors(Random rng, List<String> addresseeIds) {
        List<Debitor> records = new ArrayList<>();
        for (int index = 0; index < DEBITORS_PER_SCOPE; index++) {
            Creditor shared = buildBusinessPartnerAsCreditor(rng, addresseeIds, index, "DBT%03d", 80000);
            records.add(new Debitor(
                    shared.id(), shared.accountNumber(), shared.addresseeId(), shared.businessPartnerNumber(),
                    shared.businessPartnerRelationId(), shared.caption(), shared.dateLastModification(),
                    shared.isBusinessPartnerActive(), shared.isOrganizationBusinessPartner(),
                    shared.legalEntityType(), shared.shortName(), shared.accountingInformation(),
                    shared.addresses(), shared.alternativeSearchName(), shared.banks(), shared.communications(),
                    shared.complimentaryClose(), shared.correspondenceTitle(), shared.euVatIdCountryCode(),
                    shared.euVatIdNumber(), shared.legalPerson(), shared.naturalPerson(),
                    shared.notSpecifiedPerson(), shared.salutation(), shared.thirdPartyNumber()));
        }
        return List.copyOf(records);
    }

    private Creditor buildBusinessPartnerAsCreditor(
            Random rng, List<String> addresseeIds, int index, String idFormat, int accountBase) {
        String legalEntityType;
        if (index == 0) {
            legalEntityType = "natural_person";
        } else if (index == 1) {
            legalEntityType = "legal_person";
        } else {
            legalEntityType = rng.nextBoolean() ? "natural_person" : "legal_person";
        }

        int accountNumber = accountBase + index;
        String addresseeId = addresseeIds.isEmpty() ? null : pick(rng, addresseeIds);
        String shortName = pick(rng, PERSON_NAME_POOL);

        return new Creditor(
                String.format(idFormat, index + 1),
                accountNumber,
                addresseeId,
                String.valueOf(accountNumber),
                null,
                null,
                null,
                true,
                "legal_person".equals(legalEntityType),
                legalEntityType,
                shortName,
                null,
                List.of(),
                null,
                List.of(),
                List.of(),
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
        );
    }

    private List<GeneralLedgerAccount> generateGeneralLedgerAccounts(Random rng) {
        List<GeneralLedgerAccount> records = new ArrayList<>();
        for (int index = 0; index < GL_ACCOUNTS_PER_SCOPE; index++) {
            int accountNumber = 1000 + index;
            records.add(new GeneralLedgerAccount(
                    String.valueOf(accountNumber),
                    accountNumber,
                    "Sachkonto " + (index + 1),
                    1,
                    1,
                    0,
                    0,
                    null,
                    List.of()));
        }
        return List.copyOf(records);
    }

    private List<AccountingSequenceProcessed> generateAccountingSequencesProcessed(Random rng) {
        List<AccountingSequenceProcessed> records = new ArrayList<>();
        for (int index = 0; index < ACCOUNTING_SEQUENCES_PER_SCOPE; index++) {
            String id = String.valueOf(500 + index);
            records.add(new AccountingSequenceProcessed(
                    id,
                    "Buchungsstapel",
                    id,
                    "2024-01-1" + index + "T00:00:00.000+01:00",
                    "2024-01-01T00:00:00.000+01:00",
                    "2024-12-31T00:00:00.000+01:00",
                    "Sequenz " + (index + 1),
                    "geprueft",
                    true,
                    "manuell",
                    "Finanzbuchfuehrung",
                    null,
                    null));
        }
        return List.copyOf(records);
    }

    private List<AccountingTransactionKey> generateAccountingTransactionKeys(Random rng) {
        List<AccountingTransactionKey> records = new ArrayList<>();
        for (int index = 0; index < TRANSACTION_KEYS_PER_SCOPE; index++) {
            records.add(new AccountingTransactionKey(
                    String.valueOf(index + 1),
                    "keine",
                    "Buchungsschluessel " + (index + 1),
                    0,
                    "2024-01-01T00:00:00.000+01:00",
                    "2024-12-31T00:00:00.000+01:00",
                    "Standard",
                    rng.nextBoolean(),
                    index + 1,
                    19.0));
        }
        return List.copyOf(records);
    }

    private List<OpenItem> generateOpenItems(
            Random rng, boolean receivable, List<String> termOfPaymentIds,
            List<String> accountingSequenceIds, List<String> costCenterIds) {
        List<OpenItem> records = new ArrayList<>();
        for (int index = 0; index < OPEN_ITEMS_PER_SCOPE; index++) {
            boolean isDebit = index % 2 == 0;
            double amount = Math.round((50.0 + rng.nextDouble() * 500.0) * 100.0) / 100.0;
            String accountingSequenceId = accountingSequenceIds.isEmpty()
                    ? String.valueOf(500 + index) : pick(rng, accountingSequenceIds);

            records.add(new OpenItem(
                    String.valueOf((receivable ? 6000 : 5000) + index),
                    (receivable ? 10000 : 70000) + index,
                    accountingSequenceId,
                    "2024-0" + (1 + index % 9) + "-15T00:00:00.000+01:00",
                    isDebit ? "S" : "H",
                    "Beleg " + (index + 1),
                    "Rechnung",
                    false,
                    false,
                    false,
                    amount,
                    String.valueOf(index + 1),
                    "Ueberweisung",
                    "Posting " + (index + 1),
                    index + 1,
                    19.0,
                    amount,
                    "EUR",
                    isDebit ? null : amount,
                    isDebit ? amount : null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    false,
                    costCenterIds.isEmpty() ? null : pick(rng, costCenterIds),
                    termOfPaymentIds.isEmpty() ? null : Integer.parseInt(pick(rng, termOfPaymentIds)),
                    null,
                    null,
                    null,
                    null,
                    null,
                    null
            ));
        }
        return List.copyOf(records);
    }

    private List<AssetStocktaking> generateAssetStocktakings(
            Random rng, List<GeneralLedgerAccount> generalLedgerAccounts) {
        List<AssetStocktaking> records = new ArrayList<>();
        for (int index = 0; index < ASSET_STOCKTAKINGS_PER_SCOPE; index++) {
            GeneralLedgerAccount account = generalLedgerAccounts.isEmpty() ? null
                    : generalLedgerAccounts.get(index % generalLedgerAccounts.size());
            com.elo.datevmock.model.GeneralLedgerAccountMinimal minimal = account == null ? null
                    : new com.elo.datevmock.model.GeneralLedgerAccountMinimal(account.accountNumber(), account.caption());
            records.add(new AssetStocktaking(
                    String.valueOf(index + 1),
                    9000 + index,
                    "INV-" + (index + 1),
                    1,
                    minimal,
                    "Inventar " + (index + 1),
                    Math.round((100.0 + rng.nextDouble() * 900.0) * 100.0) / 100.0,
                    1.0,
                    "2024-06-01T00:00:00.000+01:00",
                    "Stueck",
                    "Lager " + (index + 1),
                    "gut",
                    null, null, null, null, null, null, null, null, null, null, null, null
            ));
        }
        return List.copyOf(records);
    }

    private List<PostingProposalRule> generatePostingProposalRules(
            Random rng, boolean outgoing, List<AccountingTransactionKey> transactionKeys,
            List<GeneralLedgerAccount> generalLedgerAccounts) {
        List<PostingProposalRule> records = new ArrayList<>();
        for (int index = 0; index < PROPOSAL_RULES_PER_SCOPE; index++) {
            int transactionKeyNumber = transactionKeys.isEmpty() ? index + 1 : transactionKeys.get(index % transactionKeys.size()).number();
            int accountNumber = generalLedgerAccounts.isEmpty() ? 1000 + index : generalLedgerAccounts.get(index % generalLedgerAccounts.size()).accountNumber();

            com.elo.datevmock.model.AssignmentCriteria criteria =
                    new com.elo.datevmock.model.AssignmentCriteria("Regel " + (index + 1), 19.0, null);
            com.elo.datevmock.model.PostingProposalInformation info =
                    new com.elo.datevmock.model.PostingProposalInformation(
                            transactionKeyNumber, accountNumber,
                            outgoing ? "manuell" : "automatisch", null, null, null, null);

            records.add(new PostingProposalRule(
                    String.valueOf((outgoing ? 200 : 100) + index),
                    rng.nextBoolean(),
                    criteria,
                    List.of(info),
                    "2024-01-01T00:00:00.000+01:00",
                    null));
        }
        return List.copyOf(records);
    }

    private List<CostCenter> generateCostCenters(Random rng) {
        List<CostCenter> records = new ArrayList<>();
        for (int index = 0; index < COST_CENTERS_PER_SCOPE; index++) {
            int creationYear = 2016 + index;
            String responsible = pick(rng, PERSON_NAME_POOL);
            double rateValue = Math.round((30.0 + rng.nextDouble() * 25.0) * 100.0) / 100.0;

            List<CostRate> costRates = index % 2 == 0
                    ? List.of(new CostRate(
                            Integer.parseInt(creationYear + "1201"),
                            Integer.parseInt((creationYear + 1) + "1130"),
                            rateValue))
                    : List.of();

            records.add(new CostCenter(
                    String.format("KST%03d", index + 1),
                    "Kostenstelle " + (index + 1) + " Verwaltung",
                    "KST" + (index + 1),
                    creationYear + "-01-15T00:00:00.000+01:00",
                    costRates,
                    List.of(),
                    creationYear + "-06-01T00:00:00.000+01:00",
                    null,
                    null,
                    null,
                    null,
                    null,
                    responsible
            ));
        }
        return List.copyOf(records);
    }

    private static String pick(Random rng, List<String> values) {
        return values.get(rng.nextInt(values.size()));
    }
}
