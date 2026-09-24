package com.elo.datevmock.model;

import java.util.List;

/** Ports {@code app/models.py::AssetStocktaking}. */
public record AssetStocktaking(
        String id,
        int assetNumber,
        String inventoryNumber,
        int accountingReason,
        GeneralLedgerAccountMinimal generalLedgerAccount,
        String inventoryName,
        Double price,
        Double quantity,
        String stocktakingDate,
        String unit,
        String location,
        String condition,
        String acquisitionDate,
        Integer economicLifetime,
        String kost1CostCenterId,
        Integer branch,
        String orderDate,
        String originType,
        String farmlandNumber,
        String serialNumber,
        String contractNumber,
        String typeOfUse,
        String isin,
        String explanationOfDepreciation
) {

    /** Ports {@code ASSET_STOCKTAKING_FIELD_ORDER}; {@code generalLedgerAccount} (nested) excluded, same as CostCenter's cost_rates. */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountingReason",
            "assetNumber",
            "condition",
            "inventoryName",
            "inventoryNumber",
            "location",
            "price",
            "quantity",
            "stocktakingDate",
            "unit"
    );
}
