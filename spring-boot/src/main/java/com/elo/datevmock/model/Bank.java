package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::Bank} — master-data {@code Bank}, full flat
 * schema (small, no nesting). Distinct from {@link BusinessPartnerBank}
 * (SB2), which is a Creditor/Debitor-nested resource, not this top-level
 * master-data one.
 */
public record Bank(
        String id,
        String bankCode,
        String bic,
        String city,
        String countryCode,
        String name,
        boolean standard,
        String timestamp
) {
}
