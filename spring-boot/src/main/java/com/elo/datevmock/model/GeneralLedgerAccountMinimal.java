package com.elo.datevmock.model;

/** Ports {@code app/models.py::GeneralLedgerAccountMinimal} (JSON-only, nested under {@link AssetStocktaking}). */
public record GeneralLedgerAccountMinimal(
        int accountNumber,
        String caption
) {
}
