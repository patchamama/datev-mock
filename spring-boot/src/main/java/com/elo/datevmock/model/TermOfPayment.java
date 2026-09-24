package com.elo.datevmock.model;

/**
 * Minimal port of {@code app/models.py::TermOfPayment} — only {@code id}
 * and {@code caption}, the two fields SB3's cross-scope backfill
 * (`FiscalYear.creditorTermOfPaymentId`) actually needs to exercise. The
 * remaining real fields ({@code dueType}/{@code dueInDays}/
 * {@code dueAsPeriod}/{@code cashDiscount*Percentage}) belong to SB6
 * (accounting read API parity), which will expand this record to full
 * fidelity when the real HTTP endpoint is ported.
 */
public record TermOfPayment(
        String id,
        String caption
) {
}
