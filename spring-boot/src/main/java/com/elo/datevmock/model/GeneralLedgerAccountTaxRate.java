package com.elo.datevmock.model;

/** Ports {@code app/models.py::GeneralLedgerAccountTaxRate} (JSON-only, excluded from XML). */
public record GeneralLedgerAccountTaxRate(
        double taxRate,
        String validFrom,
        String validTo
) {
}
