package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::BusinessPartnerBank} (`datev.bank` --
 * creditor/debitor `banks[]` item). Not the master-data `Bank` shape.
 */
public record BusinessPartnerBank(
        String id,
        String bankAccountNumber,
        String bankCode,
        String bankName,
        String bic,
        Integer businessPartnerBankPosition,
        String countryCode,
        String differingAccountHolder,
        String iban,
        Boolean isBusinessPartnerBank,
        String sepaMandateReference,
        String note,
        String validFrom,
        String validTo
) {
}
