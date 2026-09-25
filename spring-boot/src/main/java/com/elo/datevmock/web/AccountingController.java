package com.elo.datevmock.web;

import com.elo.datevmock.json.DatevJsonMapper;
import com.elo.datevmock.masterdata.MasterDataGenerator;
import com.elo.datevmock.model.AccountingClient;
import com.elo.datevmock.model.Addressee;
import com.elo.datevmock.model.AccountingTransactionKey;
import com.elo.datevmock.model.AssetStocktaking;
import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.model.Creditor;
import com.elo.datevmock.model.Debitor;
import com.elo.datevmock.model.GeneralLedgerAccount;
import com.elo.datevmock.model.TermOfPayment;
import com.elo.datevmock.negotiation.FormatNegotiator;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.scoped.AccountingClientGenerator;
import com.elo.datevmock.scoped.AccountingClientJson;
import com.elo.datevmock.scoped.ScopedDataService;
import com.elo.datevmock.settings.MockSettings;
import com.elo.datevmock.store.RecordMapper;
import com.elo.datevmock.store.ReferenceValidation;
import com.elo.datevmock.store.StoredRecordStore;
import com.elo.datevmock.store.ValidationException;
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
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.function.Supplier;
import java.util.stream.Collectors;

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

    // Ports `_BUSINESS_PARTNER_NIL_FIELDS`: nested object/array fields with
    // no dedicated XML sub-rendering, forced null on both the generated and
    // the stored-merged Creditor/Debitor read path.
    private static final Set<String> BUSINESS_PARTNER_NIL_FIELDS = Set.of(
            "naturalPerson", "legalPerson", "notSpecifiedPerson", "addresses", "banks", "communications",
            "accountingInformation");

    // SB12: shares the same StoredRecordStore rows AdminDataStore now writes
    // through for admin-panel accounting-client CRUD, instead of this GET
    // reading only AccountingClientGenerator's fixed fake dataset.
    private static final String CLIENTS_RESOURCE = "accounting.clients";
    private static final String CREDITORS_RESOURCE = "accounting.creditors";
    private static final String DEBITORS_RESOURCE = "accounting.debitors";
    private static final String TERMS_OF_PAYMENT_RESOURCE = "accounting.terms_of_payment";
    private static final String COST_CENTERS_RESOURCE = "accounting.cost_centers";
    private static final String ASSETS_STOCKTAKINGS_RESOURCE = "accounting.assets_stocktakings";
    private static final String GENERAL_LEDGER_ACCOUNTS_RESOURCE = "accounting.general_ledger_accounts";
    private static final String ACCOUNTING_TRANSACTION_KEYS_RESOURCE = "accounting.accounting_transaction_keys";
    private static final String POSTING_PROPOSALS_INCOMING_RESOURCE = "accounting.posting_proposals_incoming_invoices";
    private static final String POSTING_PROPOSALS_OUTGOING_RESOURCE = "accounting.posting_proposals_outgoing_invoices";

    private final ScopedDataService scopedData;
    private final AccountingClientGenerator clientGenerator;
    private final OverrideStore overrides;
    private final MockSettings settings;
    private final StoredRecordStore store;
    private final MasterDataGenerator masterDataGenerator;
    private final ObjectMapper jsonMapper = DatevJsonMapper.create();
    private final ObjectMapper plainJsonMapper = new ObjectMapper();

    public AccountingController(
            ScopedDataService scopedData, AccountingClientGenerator clientGenerator,
            OverrideStore overrides, MockSettings settings, StoredRecordStore store,
            MasterDataGenerator masterDataGenerator) {
        this.scopedData = scopedData;
        this.clientGenerator = clientGenerator;
        this.overrides = overrides;
        this.settings = settings;
        this.store = store;
        this.masterDataGenerator = masterDataGenerator;
    }

    @GetMapping("/clients")
    public ResponseEntity<String> getClients(@RequestHeader(value = "Accept", required = false) String accept) {
        return respond(CLIENTS_RESOURCE, accept,
                () -> RecordMapper.mergeWithStored(
                        clientGenerator.clients(), CLIENTS_RESOURCE, AccountingClient.class,
                        "id", Map.of(), Set.of(), store, null, null),
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
                    List<CostCenter> records = mergedCostCenters(clientId, fiscalYearId, costSystemId);
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
                () -> mergedCreditors(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                CreditorXmlSerializer::serialize);
    }

    @GetMapping("/clients/{clientId}/fiscal-years/{fiscalYearId}/debitors")
    public ResponseEntity<String> getDebitors(
            @PathVariable String clientId, @PathVariable String fiscalYearId,
            @RequestHeader(value = "Accept", required = false) String accept) {
        return respond("accounting.debitors", accept,
                () -> mergedDebitors(clientId, fiscalYearId),
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
                () -> mergedAssetsStocktakings(clientId, fiscalYearId),
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
                () -> mergedTermsOfPayment(clientId, fiscalYearId),
                records -> writeJson(jsonMapper, records),
                TermOfPaymentXmlSerializer::serialize);
    }

    // --- SB7: accounting write API parity -------------------------------------
    //
    // Ports `app/routers/accounting.py`'s P2/P3 write endpoints (`_write_record`
    // + `_validate_reference`/`_validate_business_partner_write`), representative
    // families named in the epic scope: partners (creditors/debitors), terms of
    // payment, cost centers, asset stocktaking, and the incoming/outgoing
    // posting-proposal batches. Every write is scoped by client_id/fiscal_year_id
    // (SB4's `StoredRecordStore`) so it's visible on a subsequent GET through the
    // merge helpers above, and survives a restart the same way SB4 already proved.
    // Not implemented (documented gap, see epic doc): cost-sequences,
    // cost-center-properties, cost-accounting-records, various-addresses,
    // internal-cost-services, accounting-sequences (create-only, no GET), and the
    // cash-register posting-proposal batch -- same `_write_record` pattern, lower
    // priority per the "breadth over exhaustive depth" mandate.

    @PostMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/debitors", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postDebitor(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody Map<String, Object> body) {
        validateBusinessPartnerWrite(body, clientId, fiscalYearId);
        return writeScopedRecord(DEBITORS_RESOURCE, body, null, clientId, fiscalYearId);
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/debitors", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<Map<String, Object>> putDebitors(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody List<Map<String, Object>> body) {
        return body.stream().map(item -> {
            validateBusinessPartnerWrite(item, clientId, fiscalYearId);
            return writeScopedRecord(DEBITORS_RESOURCE, item, null, clientId, fiscalYearId);
        }).collect(Collectors.toList());
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/debitors/{debitorId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putDebitor(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String debitorId,
            @RequestBody Map<String, Object> body) {
        validateBusinessPartnerWrite(body, clientId, fiscalYearId);
        return writeScopedRecord(DEBITORS_RESOURCE, body, debitorId, clientId, fiscalYearId);
    }

    @PostMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/creditors", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postCreditor(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody Map<String, Object> body) {
        validateBusinessPartnerWrite(body, clientId, fiscalYearId);
        return writeScopedRecord(CREDITORS_RESOURCE, body, null, clientId, fiscalYearId);
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/creditors", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<Map<String, Object>> putCreditors(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody List<Map<String, Object>> body) {
        return body.stream().map(item -> {
            validateBusinessPartnerWrite(item, clientId, fiscalYearId);
            return writeScopedRecord(CREDITORS_RESOURCE, item, null, clientId, fiscalYearId);
        }).collect(Collectors.toList());
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/creditors/{creditorId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putCreditor(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String creditorId,
            @RequestBody Map<String, Object> body) {
        validateBusinessPartnerWrite(body, clientId, fiscalYearId);
        return writeScopedRecord(CREDITORS_RESOURCE, body, creditorId, clientId, fiscalYearId);
    }

    @PostMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/terms-of-payment", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postTermOfPayment(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody Map<String, Object> body) {
        requireField(body, "caption");
        return writeScopedRecord(TERMS_OF_PAYMENT_RESOURCE, body, null, clientId, fiscalYearId);
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/terms-of-payment/{termOfPaymentId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putTermOfPayment(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String termOfPaymentId,
            @RequestBody Map<String, Object> body) {
        return writeScopedRecord(TERMS_OF_PAYMENT_RESOURCE, body, termOfPaymentId, clientId, fiscalYearId);
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/assets/{assetId}/stocktaking", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putAssetStocktaking(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String assetId,
            @RequestBody Map<String, Object> body) {
        requireField(body, "asset_number");
        requireField(body, "inventory_number");
        @SuppressWarnings("unchecked")
        Map<String, Object> glAccount = (Map<String, Object>) body.get("general_ledger_account");
        if (glAccount != null) {
            ReferenceValidation.validateReference(
                    asInt(glAccount.get("account_number")),
                    intCandidates(mergedGeneralLedgerAccounts(clientId, fiscalYearId), GeneralLedgerAccount::accountNumber),
                    "general_ledger_account.account_number");
        }
        ReferenceValidation.validateReference(
                body.get("kost1_cost_center_id"), primaryCostCenterIds(clientId, fiscalYearId), "kost1_cost_center_id");
        return writeScopedRecord(ASSETS_STOCKTAKINGS_RESOURCE, body, assetId, clientId, fiscalYearId);
    }

    @PutMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/cost-systems/{costSystemId}/cost-centers/{costCenterId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putCostCenter(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @PathVariable String costSystemId,
            @PathVariable String costCenterId, @RequestBody Map<String, Object> body) {
        return writeScopedRecord(COST_CENTERS_RESOURCE, body, costCenterId, clientId, fiscalYearId);
    }

    @PostMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/posting-proposals-incoming-invoices/batch", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public List<Map<String, Object>> postPostingProposalsIncomingInvoicesBatch(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody List<Map<String, Object>> body) {
        Set<Integer> transactionKeys = intCandidates(mergedAccountingTransactionKeys(clientId, fiscalYearId), AccountingTransactionKey::number);
        Set<Integer> glAccountNumbers = intCandidates(mergedGeneralLedgerAccounts(clientId, fiscalYearId), GeneralLedgerAccount::accountNumber);
        Set<Integer> creditorAccountNumbers = intCandidates(mergedCreditors(clientId, fiscalYearId), Creditor::accountNumber);
        Set<String> costCenterIds = primaryCostCenterIds(clientId, fiscalYearId);
        for (Map<String, Object> item : body) {
            requireField(item, "amount");
            requireField(item, "date");
            ReferenceValidation.validateReference(asInt(item.get("accounting_transaction_key")), transactionKeys, "accounting_transaction_key");
            ReferenceValidation.validateReference(asInt(item.get("account_number")), glAccountNumbers, "account_number");
            ReferenceValidation.validateReference(asInt(item.get("creditor_account_number")), creditorAccountNumbers, "creditor_account_number");
            ReferenceValidation.validateReference(item.get("kost1_cost_center_id"), costCenterIds, "kost1_cost_center_id");
            ReferenceValidation.validateReference(item.get("kost2_cost_center_id"), costCenterIds, "kost2_cost_center_id");
        }
        return body.stream()
                .map(item -> writeScopedRecord(POSTING_PROPOSALS_INCOMING_RESOURCE, item, null, clientId, fiscalYearId))
                .collect(Collectors.toList());
    }

    @PostMapping(value = "/clients/{clientId}/fiscal-years/{fiscalYearId}/posting-proposals-outgoing-invoices/batch", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public List<Map<String, Object>> postPostingProposalsOutgoingInvoicesBatch(
            @PathVariable String clientId, @PathVariable String fiscalYearId, @RequestBody List<Map<String, Object>> body) {
        Set<Integer> transactionKeys = intCandidates(mergedAccountingTransactionKeys(clientId, fiscalYearId), AccountingTransactionKey::number);
        Set<Integer> glAccountNumbers = intCandidates(mergedGeneralLedgerAccounts(clientId, fiscalYearId), GeneralLedgerAccount::accountNumber);
        Set<Integer> debitorAccountNumbers = intCandidates(mergedDebitors(clientId, fiscalYearId), Debitor::accountNumber);
        Set<String> costCenterIds = primaryCostCenterIds(clientId, fiscalYearId);
        for (Map<String, Object> item : body) {
            requireField(item, "amount");
            requireField(item, "date");
            ReferenceValidation.validateReference(asInt(item.get("accounting_transaction_key")), transactionKeys, "accounting_transaction_key");
            ReferenceValidation.validateReference(asInt(item.get("account_number")), glAccountNumbers, "account_number");
            ReferenceValidation.validateReference(asInt(item.get("debitor_account_number")), debitorAccountNumbers, "debitor_account_number");
            ReferenceValidation.validateReference(item.get("kost1_cost_center_id"), costCenterIds, "kost1_cost_center_id");
            ReferenceValidation.validateReference(item.get("kost2_cost_center_id"), costCenterIds, "kost2_cost_center_id");
        }
        return body.stream()
                .map(item -> writeScopedRecord(POSTING_PROPOSALS_OUTGOING_RESOURCE, item, null, clientId, fiscalYearId))
                .collect(Collectors.toList());
    }

    // --- SB7: merge-aware read helpers (5 of 16 scoped resources merge SQLite
    // overlays in the Python original: cost_centers, creditors, debitors,
    // assets_stocktakings, terms_of_payment) -------------------------------

    private List<CostCenter> mergedCostCenters(String clientId, String fiscalYearId, String costSystemId) {
        return RecordMapper.mergeWithStored(
                scopedData.getCostCentersForScope(clientId, fiscalYearId, costSystemId), COST_CENTERS_RESOURCE,
                CostCenter.class, "id", Map.of(), Set.of(), store, clientId, fiscalYearId);
    }

    private List<Creditor> mergedCreditors(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getCreditorsForScope(clientId, fiscalYearId), CREDITORS_RESOURCE,
                Creditor.class, "id", Map.of(), BUSINESS_PARTNER_NIL_FIELDS, store, clientId, fiscalYearId);
    }

    private List<Debitor> mergedDebitors(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getDebitorsForScope(clientId, fiscalYearId), DEBITORS_RESOURCE,
                Debitor.class, "id", Map.of(), BUSINESS_PARTNER_NIL_FIELDS, store, clientId, fiscalYearId);
    }

    private List<TermOfPayment> mergedTermsOfPayment(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getTermsOfPaymentForScope(clientId, fiscalYearId), TERMS_OF_PAYMENT_RESOURCE,
                TermOfPayment.class, "id", Map.of(), Set.of(), store, clientId, fiscalYearId);
    }

    private List<AssetStocktaking> mergedAssetsStocktakings(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getAssetsStocktakingsForScope(clientId, fiscalYearId), ASSETS_STOCKTAKINGS_RESOURCE,
                AssetStocktaking.class, "id", Map.of(), Set.of(), store, clientId, fiscalYearId);
    }

    private List<GeneralLedgerAccount> mergedGeneralLedgerAccounts(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getGeneralLedgerAccountsForScope(clientId, fiscalYearId), GENERAL_LEDGER_ACCOUNTS_RESOURCE,
                GeneralLedgerAccount.class, "id", Map.of(), Set.of(), store, clientId, fiscalYearId);
    }

    private List<AccountingTransactionKey> mergedAccountingTransactionKeys(String clientId, String fiscalYearId) {
        return RecordMapper.mergeWithStored(
                scopedData.getAccountingTransactionKeysForScope(clientId, fiscalYearId), ACCOUNTING_TRANSACTION_KEYS_RESOURCE,
                AccountingTransactionKey.class, "id", Map.of(), Set.of(), store, clientId, fiscalYearId);
    }

    /** Ports `_primary_cost_center_ids`: the fiscal year's first cost system's cost-center ids. */
    private Set<String> primaryCostCenterIds(String clientId, String fiscalYearId) {
        List<com.elo.datevmock.model.CostSystem> costSystems = scopedData.getCostSystemsForScope(clientId, fiscalYearId);
        String primaryCostSystemId = costSystems.get(0).id();
        return mergedCostCenters(clientId, fiscalYearId, primaryCostSystemId).stream()
                .map(CostCenter::id).collect(Collectors.toSet());
    }

    private Set<String> addresseeIds() {
        return masterDataGenerator.addressees().stream().map(Addressee::id).collect(Collectors.toSet());
    }

    /** Ports `_validate_business_partner_write`: addressee_id + accounting_information.term_of_payment_id FK checks. */
    private void validateBusinessPartnerWrite(Map<String, Object> body, String clientId, String fiscalYearId) {
        ReferenceValidation.validateReference(body.get("addressee_id"), addresseeIds(), "addressee_id");
        @SuppressWarnings("unchecked")
        Map<String, Object> accountingInformation = (Map<String, Object>) body.get("accounting_information");
        if (accountingInformation != null) {
            Set<Integer> termOfPaymentIds = intCandidatesFromIds(mergedTermsOfPayment(clientId, fiscalYearId).stream().map(TermOfPayment::id));
            ReferenceValidation.validateReference(
                    asInt(accountingInformation.get("term_of_payment_id")), termOfPaymentIds,
                    "accounting_information.term_of_payment_id");
        }
    }

    private void requireField(Map<String, Object> body, String fieldName) {
        if (body.get(fieldName) == null) {
            throw new ValidationException(fieldName + ": field required");
        }
    }

    private Map<String, Object> writeScopedRecord(
            String resourceType, Map<String, Object> body, String recordId, String clientId, String fiscalYearId) {
        String resolvedId = recordId != null ? recordId
                : (body.get("id") != null ? String.valueOf(body.get("id")) : UUID.randomUUID().toString());
        body.put("id", resolvedId);
        return store.upsertRecord(resourceType, resolvedId, body, clientId, fiscalYearId);
    }

    private <T> Set<Integer> intCandidates(List<T> records, Function<T, Integer> extractor) {
        return records.stream().map(extractor).filter(java.util.Objects::nonNull).collect(Collectors.toSet());
    }

    private Set<Integer> intCandidatesFromIds(java.util.stream.Stream<String> ids) {
        return ids.map(this::asInt).filter(java.util.Objects::nonNull).collect(Collectors.toSet());
    }

    /** Best-effort int coercion (ports `_as_int`): a non-numeric id simply never matches an int-typed reference. */
    private Integer asInt(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            return null;
        }
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
