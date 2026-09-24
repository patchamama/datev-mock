package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::TermOfPayment}. {@code dueInDays}/
 * {@code dueAsPeriod} (nested optional objects) are deliberately not
 * modeled -- same as the Python source, they're excluded from
 * {@code TERM_OF_PAYMENT_FIELD_ORDER} and stay JSON-only/unrendered in
 * this mock (no real XML evidence for a nested shape).
 */
public record TermOfPayment(
        String id,
        String caption,
        String dueType,
        Double cashDiscount1Percentage,
        Double cashDiscount2Percentage
) {

    public TermOfPayment(String id, String caption) {
        this(id, caption, "due_in_days", null, null);
    }

    /** Ports {@code TERM_OF_PAYMENT_FIELD_ORDER}. */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "caption",
            "cashDiscount1Percentage",
            "cashDiscount2Percentage",
            "dueType"
    );
}
