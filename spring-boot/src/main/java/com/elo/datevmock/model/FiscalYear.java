package com.elo.datevmock.model;

import java.util.List;

/**
 * Minimal port of {@code app/models.py::FiscalYear} — only {@code id} and
 * the two term-of-payment cross-reference fields SB3's referential-integrity
 * backfill (ports {@code app/scoped_data.py::get_fiscal_years_for_client})
 * actually needs to prove.
 *
 * <p><b>SB6 honest gap:</b> the real contract has ~20 fields
 * ({@code account_length}, {@code account_system},
 * {@code advance_turnover_tax_return}, {@code begin}, {@code end},
 * {@code client_number}, {@code consultant_number}, etc. -- see
 * {@code app/models.py::FISCAL_YEAR_FIELD_ORDER}). Given this epic's
 * breadth-over-depth mandate, only the 3 already-proven fields are
 * rendered; {@link #XML_FIELD_ORDER} below is a deliberately trimmed
 * field order (not the full spec list) so the endpoint is correctly
 * shaped, format-negotiated, and deterministically scoped -- just not yet
 * field-complete. Left as a documented follow-up, not silently dropped.
 *
 * {@code creditorTermOfPaymentId} is non-optional in the real contract (a
 * plain {@code int}); {@code debitorTermOfPaymentId} is genuinely optional
 * (a nullable {@link Integer}) — matches {@code app/models.py::FiscalYear}.
 */
public record FiscalYear(
        String id,
        int creditorTermOfPaymentId,
        Integer debitorTermOfPaymentId
) {

    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "creditorTermOfPaymentId",
            "debitorTermOfPaymentId"
    );
}
