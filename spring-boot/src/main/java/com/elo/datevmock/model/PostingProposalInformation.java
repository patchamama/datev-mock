package com.elo.datevmock.model;

/** Ports {@code app/models.py::PostingProposalInformation} (JSON-only, nested list on {@link PostingProposalRule}). */
public record PostingProposalInformation(
        int accountingTransactionKey,
        int accountNumber,
        String originOfPostingDescription,
        Integer businessPartnerAccountNumber,
        String kost1CostCenterId,
        String kost2CostCenterId,
        String postingDescription
) {
}
