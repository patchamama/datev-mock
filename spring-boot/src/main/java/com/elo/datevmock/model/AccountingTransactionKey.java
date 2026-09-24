package com.elo.datevmock.model;

import java.util.List;

/** Ports {@code app/models.py::AccountingTransactionKey} (no optional fields -- 100% presence per real evidence). */
public record AccountingTransactionKey(
        String id,
        String additionalFunction,
        String caption,
        int casesRelatedToGoodsAndServices,
        String dateFrom,
        String dateTo,
        String group,
        boolean isTaxRateSelectable,
        int number,
        double taxRate
) {

    /** Ports {@code ACCOUNTING_TRANSACTION_KEY_FIELD_ORDER}. */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "additionalFunction",
            "caption",
            "casesRelatedToGoodsAndServices",
            "dateFrom",
            "dateTo",
            "group",
            "isTaxRateSelectable",
            "number",
            "taxRate"
    );
}
