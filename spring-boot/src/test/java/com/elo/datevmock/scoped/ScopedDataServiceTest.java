package com.elo.datevmock.scoped;

import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.model.CostSystem;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.FiscalYear;
import com.elo.datevmock.model.TermOfPayment;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports {@code app/scoped_data.py}'s deterministic per-scope generation and
 * caching: same scope key -&gt; identical repeated reads (same cached list
 * instance); distinct scope keys -&gt; independently cached entries; cross-
 * references (creditor's {@code addresseeId}, fiscal year's
 * {@code creditorTermOfPaymentId}) point at real records within the same
 * scope. True random-content divergence between distinct scope keys is
 * proven once, at the seed level, by {@link ScopeSeedTest} — SHA256 makes
 * that deterministic and collision-free, unlike asserting inequality of a
 * downstream generated field (e.g. a name drawn from a small pool), which
 * would carry a real, if small, chance of an unlucky coincidental match for
 * two arbitrary fixed test scope keys.
 */
class ScopedDataServiceTest {

    private final ScopedDataService service = new ScopedDataService();

    @Test
    void repeatedCostCenterReadsForSameScopeReturnTheSameCachedList() {
        List<CostCenter> first = service.getCostCentersForScope("client-a", "2024", "1");
        List<CostCenter> second = service.getCostCentersForScope("client-a", "2024", "1");

        assertSame(first, second, "same scope key must return the same cached list instance");
    }

    @Test
    void distinctCostCenterScopesAreCachedIndependently() {
        List<CostCenter> scopeA = service.getCostCentersForScope("client-a", "2024", "1");
        List<CostCenter> scopeB = service.getCostCentersForScope("client-b", "2099", "1");
        List<CostCenter> scopeC = service.getCostCentersForScope("client-a", "2024", "2");

        assertNotSame(scopeA, scopeB, "distinct client/fiscal-year scope keys must be cached separately");
        assertNotSame(scopeA, scopeC, "distinct cost-system scope keys must be cached separately");
    }

    @Test
    void creditorAddresseeIdReferencesTheGlobalAddresseePool() {
        List<Creditor> creditors = service.getCreditorsForScope("client-a", "2024");
        assertTrue(creditors.size() > 0);

        for (Creditor creditor : creditors) {
            assertTrue(
                    GlobalAddresseePool.ADDRESSEE_IDS.contains(creditor.addresseeId()),
                    "creditor.addresseeId() must reference a real id from the global addressee pool");
        }
    }

    @Test
    void repeatedCreditorReadsForSameScopeReturnTheSameCachedList() {
        List<Creditor> first = service.getCreditorsForScope("client-a", "2024");
        List<Creditor> second = service.getCreditorsForScope("client-a", "2024");

        assertSame(first, second);
    }

    @Test
    void distinctCreditorScopesAreCachedIndependently() {
        List<Creditor> scopeA = service.getCreditorsForScope("client-a", "2024");
        List<Creditor> scopeB = service.getCreditorsForScope("client-b", "2099");

        assertNotSame(scopeA, scopeB);
    }

    @Test
    void fiscalYearCreditorTermOfPaymentIdIsBackfilledFromTheSameFiscalYearsOwnTermsOfPayment() {
        List<FiscalYear> fiscalYears = service.getFiscalYearsForClient("client-a");
        assertTrue(fiscalYears.size() > 0);

        for (FiscalYear fiscalYear : fiscalYears) {
            List<TermOfPayment> scopeTerms =
                    service.getTermsOfPaymentForScope("client-a", fiscalYear.id());
            List<String> termIds = scopeTerms.stream().map(TermOfPayment::id).toList();

            assertTrue(
                    termIds.contains(String.valueOf(fiscalYear.creditorTermOfPaymentId())),
                    "creditorTermOfPaymentId must reference one of this fiscal year's own terms of payment");
        }
    }

    @Test
    void repeatedFiscalYearReadsForSameClientReturnTheSameCachedList() {
        List<FiscalYear> first = service.getFiscalYearsForClient("client-a");
        List<FiscalYear> second = service.getFiscalYearsForClient("client-a");

        assertSame(first, second);
    }

    @Test
    void distinctClientsAreCachedIndependently() {
        List<FiscalYear> clientA = service.getFiscalYearsForClient("client-a");
        List<FiscalYear> clientOther = service.getFiscalYearsForClient("client-completely-different");

        assertNotSame(clientA, clientOther);
    }

    @Test
    void costSystemsForScopeAreStableAndNonEmpty() {
        List<CostSystem> costSystems = service.getCostSystemsForScope("client-a", "2024");
        assertTrue(costSystems.size() > 0);
        assertSame(costSystems, service.getCostSystemsForScope("client-a", "2024"));
    }
}
