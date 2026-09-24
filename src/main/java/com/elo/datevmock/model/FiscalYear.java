package com.elo.datevmock.model;

/**
 * Minimal port of {@code app/models.py::FiscalYear} — only {@code id} and
 * the two term-of-payment cross-reference fields SB3's referential-integrity
 * backfill (ports {@code app/scoped_data.py::get_fiscal_years_for_client})
 * actually needs to prove. The remaining 20 real fields belong to SB6
 * (accounting read API parity), which will expand this record to full
 * fidelity when the real HTTP endpoint is ported.
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
}
