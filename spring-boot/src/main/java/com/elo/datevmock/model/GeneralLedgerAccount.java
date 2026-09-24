package com.elo.datevmock.model;

import java.util.List;

/** Ports {@code app/models.py::GeneralLedgerAccount}. */
public record GeneralLedgerAccount(
        String id,
        int accountNumber,
        String caption,
        int mainFunction,
        int mainFunctionNumber,
        int functionExtension,
        Integer additionalFunction,
        String functionDescription,
        List<GeneralLedgerAccountTaxRate> taxRates
) {

    /** Ports {@code GENERAL_LEDGER_ACCOUNT_FIELD_ORDER}; {@code taxRates} excluded (JSON-only, no real XML evidence). */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountNumber",
            "additionalFunction",
            "caption",
            "functionDescription",
            "functionExtension",
            "mainFunction",
            "mainFunctionNumber"
    );
}
