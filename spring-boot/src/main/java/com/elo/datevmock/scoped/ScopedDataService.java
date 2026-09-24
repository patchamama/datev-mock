package com.elo.datevmock.scoped;

import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.model.CostRate;
import com.elo.datevmock.model.CostSystem;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.FiscalYear;
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
 * <p>Only cost systems, cost centers, terms of payment, creditors, and
 * fiscal years are ported here — the resource families SB3's acceptance
 * criteria actually exercise (null/collection/ordering was SB2's job;
 * *this* epic's job is "repeated reads stable", "distinct scopes
 * coherent", "cross-references real"). Debitors, general-ledger accounts,
 * accounting sequences/transaction keys, open items, asset stocktakings,
 * and posting-proposal rules are added by SB5-SB8 as each domain's HTTP
 * endpoint is actually ported, following this exact same pattern.
 */
@Component
public class ScopedDataService {

    private static final List<String> PERSON_NAME_POOL = List.of(
            "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker");

    private static final int FISCAL_YEARS_PER_CLIENT = 3;
    private static final int COST_SYSTEMS_PER_SCOPE = 3;
    private static final int TERMS_OF_PAYMENT_PER_SCOPE = 4;
    private static final int CREDITORS_PER_SCOPE = 4;
    private static final int COST_CENTERS_PER_SCOPE = 4;

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

    // --- fiscal-year scope (cost systems / terms of payment / creditors) --

    private FiscalYearScope getFiscalYearScope(String clientId, String fiscalYearId) {
        FiscalYearScopeKey key = new FiscalYearScopeKey(clientId, fiscalYearId);
        return fiscalYearScopeCache.computeIfAbsent(key, k -> buildFiscalYearScope(clientId, fiscalYearId));
    }

    private FiscalYearScope buildFiscalYearScope(String clientId, String fiscalYearId) {
        Random rng = new Random(ScopeSeed.seedFor(clientId, fiscalYearId));

        List<CostSystem> costSystems = generateCostSystems(rng);
        List<TermOfPayment> termsOfPayment = generateTermsOfPayment(rng);
        List<Creditor> creditors = generateCreditors(rng, GlobalAddresseePool.ADDRESSEE_IDS);

        // Primary cost system (architecture decision #4, ported from
        // `_get_fiscal_year_scope`): index 0 of this scope's own cost
        // systems, cached the normal way through the public accessor so
        // `getCostCentersForScope` and this internal lookup always agree.
        String primaryCostSystemId = costSystems.get(0).id();
        getCostCentersForScope(clientId, fiscalYearId, primaryCostSystemId);

        return new FiscalYearScope(costSystems, termsOfPayment, creditors);
    }

    // --- generation ---------------------------------------------------------

    private List<FiscalYear> generateFiscalYears(String clientId) {
        Random rng = new Random(ScopeSeed.seedFor(clientId));
        int baseYear = 2018 + rng.nextInt(7);

        List<FiscalYear> records = new ArrayList<>();
        for (int index = 0; index < FISCAL_YEARS_PER_CLIENT; index++) {
            int year = baseYear + index;
            String id = year + "0101";

            // creditor_term_of_payment_id/debitor_term_of_payment_id are
            // backfilled from *this fiscal year's own* generated scope
            // (architecture decision #4) -- resolve that scope first.
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
            records.add(new TermOfPayment(String.valueOf(9000 + index), "Zahlungsbedingung " + (index + 1)));
        }
        return List.copyOf(records);
    }

    private List<Creditor> generateCreditors(Random rng, List<String> addresseeIds) {
        List<Creditor> records = new ArrayList<>();
        for (int index = 0; index < CREDITORS_PER_SCOPE; index++) {
            String legalEntityType;
            if (index == 0) {
                legalEntityType = "natural_person";
            } else if (index == 1) {
                legalEntityType = "legal_person";
            } else {
                legalEntityType = rng.nextBoolean() ? "natural_person" : "legal_person";
            }

            int accountNumber = 70000 + index;
            String addresseeId = addresseeIds.isEmpty() ? null : pick(rng, addresseeIds);
            String shortName = pick(rng, PERSON_NAME_POOL);

            records.add(new Creditor(
                    String.format("KRD%03d", index + 1),
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
            ));
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
