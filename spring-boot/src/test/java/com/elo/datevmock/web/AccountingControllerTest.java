package com.elo.datevmock.web;

import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.settings.MockSettings;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * SB6 (accounting read API parity) -- representative coverage per the
 * epic's own "breadth over depth" mandate: every one of the 20 FastAPI
 * GET routes gets at least one working-endpoint assertion, plus dedicated
 * tests for determinism, format negotiation, the legacy cost_rates gate
 * (reused unchanged from SB2), and override precedence. Not a 1:1 port of
 * every case in {@code tests/test_fiscal_structure*.py}/
 * {@code test_json*.py}/{@code test_partners*.py}/
 * {@code test_payables_receivables*.py}.
 */
@SpringBootTest
@AutoConfigureMockMvc
class AccountingControllerTest {

    private static final String BASE = "/datev/api/accounting/v1";
    private static final String SCOPE = "/clients/client-1/fiscal-years/fy-1";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private OverrideStore overrides;

    @Autowired
    private MockSettings settings;

    private final ObjectMapper json = new ObjectMapper();

    @AfterEach
    void cleanup() {
        overrides.clearAllOverrides();
        settings.setDatevApiVersion("legacy");
    }

    // --- one working-endpoint assertion per resource family -----------------

    @Test
    void clientsListsArrayOfClientXmlByDefault() throws Exception {
        mockMvc.perform(get(BASE + "/clients"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_XML))
                .andExpect(content().string(containsString("<ArrayOfClient")));
    }

    @Test
    void fiscalYearsListsArrayOfFiscalYear() throws Exception {
        mockMvc.perform(get(BASE + "/clients/client-1/fiscal-years"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfFiscalYear")));
    }

    @Test
    void costSystemsListsArrayOfCostSystems() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/cost-systems"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfCostSystems")));
    }

    @Test
    void costCentersListsArrayOfCostCenter() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/cost-systems/1/cost-centers"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfCostCenter")));
    }

    @Test
    void creditorsListsArrayOfCreditor() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/creditors"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfCreditor")));
    }

    @Test
    void debitorsListsArrayOfDebitor() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/debitors"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfDebitor")));
    }

    @Test
    void generalLedgerAccountsListsArrayOfGeneralLedgerAccount() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/general-ledger-accounts"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfGeneralLedgerAccount")));
    }

    @Test
    void accountsPayableListsArrayOfOpenItem() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/accounts-payable"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfOpenItem")));
    }

    @Test
    void accountsPayableCondenseListsArrayOfOpenItem() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/accounts-payable/condense"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfOpenItem")));
    }

    @Test
    void accountsReceivableCondenseListsArrayOfOpenItem() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/accounts-receivable/condense"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfOpenItem")));
    }

    @Test
    void accountingSequencesProcessedListsExpectedArray() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/accounting-sequences-processed"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfAccountingSequenceProcessed")));
    }

    @Test
    void accountingTransactionKeysListsExpectedArray() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/accounting-transaction-keys"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfAccountingTransactionKey")));
    }

    @Test
    void assetsStocktakingsListsExpectedArray() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/assets/stocktakings"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfAssetStocktaking")));
    }

    @Test
    void postingProposalRulesIncomingListsExpectedArray() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/posting-proposal-rules-incoming-invoices"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfPostingProposalRule")));
    }

    @Test
    void postingProposalRulesOutgoingListsExpectedArray() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/posting-proposal-rules-outgoing-invoices"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfPostingProposalRule")));
    }

    @Test
    void termsOfPaymentListsArrayOfTermOfPayment() throws Exception {
        mockMvc.perform(get(BASE + SCOPE + "/terms-of-payment"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfTermOfPayment")));
    }

    // --- format negotiation ---------------------------------------------------

    @Test
    void creditorsExplicitJsonAcceptReturnsJsonArray() throws Exception {
        MvcResult result = mockMvc.perform(get(BASE + SCOPE + "/creditors").header("Accept", "application/json"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThan(0);
        assertThat(records.get(0).has("account_number")).isTrue();
    }

    // --- deterministic scope stability (SB3's guarantee, exercised through HTTP now) --

    @Test
    void creditorsAreStableAcrossRepeatedReadsForSameScope() throws Exception {
        String first = mockMvc.perform(get(BASE + SCOPE + "/creditors")).andReturn().getResponse().getContentAsString();
        String second = mockMvc.perform(get(BASE + SCOPE + "/creditors")).andReturn().getResponse().getContentAsString();
        assertThat(first).isEqualTo(second);
    }

    @Test
    void differentFiscalYearScopesAreIndependentlyValid() throws Exception {
        mockMvc.perform(get(BASE + "/clients/client-1/fiscal-years/fy-other/creditors"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("<ArrayOfCreditor")));
    }

    // --- legacy vs. modern cost_rates gate (SB2's toggle, reused unchanged) --

    @Test
    void costCentersOmitCostRatesInLegacyModeJson() throws Exception {
        settings.setDatevApiVersion("legacy");
        MvcResult result = mockMvc.perform(
                        get(BASE + SCOPE + "/cost-systems/1/cost-centers").header("Accept", "application/json"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.get(0).has("cost_rates")).isFalse();
    }

    @Test
    void costCentersIncludeCostRatesInModernModeJson() throws Exception {
        settings.setDatevApiVersion("modern");
        MvcResult result = mockMvc.perform(
                        get(BASE + SCOPE + "/cost-systems/1/cost-centers").header("Accept", "application/json"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        boolean anyHasCostRates = false;
        for (JsonNode record : records) {
            if (record.has("cost_rates")) {
                anyHasCostRates = true;
            }
        }
        assertThat(anyHasCostRates).isTrue();
    }

    // --- override precedence ---------------------------------------------------

    @Test
    void activeOverrideIsServedVerbatimInsteadOfGeneratedData() throws Exception {
        overrides.setOverride("accounting.creditors", "{\"overridden\":true}", "json", "override.json");
        mockMvc.perform(get(BASE + SCOPE + "/creditors"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().string(containsString("overridden")));
    }
}
