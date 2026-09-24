package com.elo.datevmock.web;

import com.elo.datevmock.json.DatevJsonMapper;
import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.negotiation.FormatNegotiator;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.scoped.AccountingClientGenerator;
import com.elo.datevmock.scoped.AccountingClientJson;
import com.elo.datevmock.scoped.ScopedDataService;
import com.elo.datevmock.settings.MockSettings;
import com.elo.datevmock.xml.AccountingClientXmlSerializer;
import com.elo.datevmock.xml.AccountingSequenceProcessedXmlSerializer;
import com.elo.datevmock.xml.AccountingTransactionKeyXmlSerializer;
import com.elo.datevmock.xml.AssetStocktakingXmlSerializer;
import com.elo.datevmock.xml.CostCenterXmlSerializer;
import com.elo.datevmock.xml.CostSystemXmlSerializer;
import com.elo.datevmock.xml.CreditorXmlSerializer;
import com.elo.datevmock.xml.DebitorXmlSerializer;
import com.elo.datevmock.xml.FiscalYearXmlSerializer;
import com.elo.datevmock.xml.GeneralLedgerAccountXmlSerializer;
import com.elo.datevmock.xml.OpenItemXmlSerializer;
import com.elo.datevmock.xml.PostingProposalRuleXmlSerializer;
import com.elo.datevmock.xml.TermOfPaymentXmlSerializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.function.Function;
import java.util.function.Supplier;

/**
 * Ports {@code app/routers/accounting.py}'s 20 GET routes -- SB6 (accounting
 * read API parity). Composes SB2 (serialization/negotiation), SB3/SB6's
 * {@link ScopedDataService} (deterministic scoped generation), and
 * overrides (SB3's {@link OverrideStore}).
 *
 * <p><b>Honest SB6 scope note:</b> unlike SB5's master-data controller,
 * these read endpoints do NOT yet merge SB4's SQLite write-overlay store
 * (only 5 of the 16 scoped resources use {@code db.merge_with_stored} in
 * the Python original: cost_centers, creditors, debitors,
 * assets_stocktakings, terms_of_payment) or apply the {@code expand=all}
 * gate on creditors/debitors. Both are deferred to SB7 (accounting write
 * API parity), where the write side needs this exact merge wiring anyway --
 * wiring it once for both read and write together avoids doing it twice.
 * Every endpoint below reads through the deterministic generator only, so
 * responses are correctly shaped, scoped, and negotiated, just not yet
 * overlay-aware. {@link FiscalYear} is also field-trimmed -- see its own
 * javadoc.
 */
@RestController
@RequestMapping("/datev/api/accounting/v1")
public class AccountingController {

    private final ScopedDataService scopedData;
    private final AccountingClientGenerator clientGenerator;
    private final OverrideStore overrides;
    private final MockSettings settings;
    private final ObjectMapper jsonMapper = DatevJsonMapper.create();
    private final ObjectMapper plainJsonMapper = new ObjectMapper();

    public AccountingController(
            ScopedDataService scopedData, AccountingClientGenerator clientGenerator,
            OverrideStore overrides, MockSettings settings) {
        this.scopedData = scopedData;
        this.clientGenerator = clientGenerator;
        this.overrides = overrides;
        this.settings = settings;
    }

    @GetMapping("/clients")
    public ResponseEntity<String> getClients(@RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.clients", accept,
                () -> clientGenerator.clients(),
                records -> writeJson(plainJsonMapper, AccountingClientJson.project(records)),
                AccountingClientXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years")
    public ResponseEntity<String> getFiscalYears(
            @PathVariable String clientId, @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.fiscal_years", accept,
                () -> scopedData.getFiscalYearsForClient(clientId),
                records -> writeJson(jsonMapper, records),
                FiscalYearXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/cost-systems")
    public ResponseEntity<String> getCostSystems(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.cost_systems", accept,
                () -> scopedData.getCostSystemsForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                CostSystemXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/cost-systems/{costSystemId}/cost-centers")
    public ResponseEntity<String> getCostCenters(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String costSystemId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.cost_centers", accept,
                () -> {
                    List<CostCenter> records = scopedData.getCostCentersForScope(clientId, fiscalYearId, costSystemId);
                    if ("legacy".equals(settings.getDatevApiVersion())) {
                        records = records.stream().map(CostCenter::withoutCostRates).toList();
                    }
                    return records;
                },
                records -> writeJson(jsonMapper, records),
                CostCenterXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/creditors")
    public ResponseEntity<String> getCreditors(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.creditors", accept,
                () -> scopedData.getCreditorsForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                CreditorXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/debitors")
    public ResponseEntity<String> getDebitors(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.debitors", accept,
                () -> scopedData.getDebitorsForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                DebitorXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/general-ledger-accounts")
    public ResponseEntity<String> getGeneralLedgerAccounts(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.general_ledger_accounts", accept,
                () -> scopedData.getGeneralLedgerAccountsForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                GeneralLedgerAccountXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/accounts-payable")
    public ResponseEntity<String> getAccountsPayable(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.accounts_payable", accept,
                () -> scopedData.getAccountsPayableForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                OpenItemXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/accounts-payable/condense")
    public ResponseEntity<String> getAccountsPayableCondense(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.accounts_payable_condense", accept,
                () -> scopedData.getAccountsPayableCondenseForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                OpenItemXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/accounts-receivable/condense")
    public ResponseEntity<String> getAccountsReceivableCondense(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.accounts_receivable_condense", accept,
                () -> scopedData.getAccountsReceivableCondenseForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                OpenItemXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/accounting-sequences-processed")
    public ResponseEntity<String> getAccountingSequencesProcessed(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.accounting_sequences_processed", accept,
                () -> scopedData.getAccountingSequencesProcessedForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                AccountingSequenceProcessedXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/accounting-transaction-keys")
    public ResponseEntity<String> getAccountingTransactionKeys(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.accounting_transaction_keys", accept,
                () -> scopedData.getAccountingTransactionKeysForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                AccountingTransactionKeyXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/assets/stocktakings")
    public ResponseEntity<String> getAssetsStocktakings(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.assets_stocktakings", accept,
                () -> scopedData.getAssetsStocktakingsForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                AssetStocktakingXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/posting-proposal-rules-incoming-invoices")
    public ResponseEntity<String> getPostingProposalRulesIncoming(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.posting_proposal_rules_incoming", accept,
                () -> scopedData.getPostingProposalRulesIncomingInvoicesForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                PostingProposalRuleXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/posting-proposal-rules-outgoing-invoices")
    public ResponseEntity<String> getPostingProposalRulesOutgoing(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.posting_proposal_rules_outgoing", accept,
                () -> scopedData.getPostingProposalRulesOutgoingInvoicesForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                PostingProposalRuleXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/terms-of-payment")
    public ResponseEntity<String> getTermsOfPayment(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.terms_of_payment", accept,
                () -> scopedData.getTermsOfPaymentForScope(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                TermOfPaymentXmlSerializer::serialize);
    }

    // --- shared negotiation/override plumbing --------------------------------

    private <T> ResponseEntity<String> respond(
            String overrideKey, String accept, Supplier<List<T>> generate,
            Function<List<T>, String> toJson, Function<List<T>, String> toXml) {
        OverrideEntry override = overrides.getActiveOverride(overrideKey);
        if (override != null) {
            MediaType mediaType = "xml".equals(override.contentType()) ? MediaType.APPLICATION_XML : MediaType.APPLICATION_JSON;
            return ResponseEntity.ok().contentType(mediaType).body(override.content());
        }

        List<T> records = generate.get();
        String format = FormatNegotiator.negotiate(accept, settings.getDefaultAccountingFormat());
        if ("json".equals(format)) {
            return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(toJson.apply(records));
        }
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_XML).body(toXml.apply(records));
    }

    private String writeJson(ObjectMapper mapper, Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize accounting JSON response", e);
        }
    }
}
