package com.elo.datevmock.model;

import java.util.List;

/** Ports {@code app/models.py::AccountingSequenceProcessed}. */
public record AccountingSequenceProcessed(
        String id,
        String accountingReason,
        String accountingSequenceId,
        String dateCommitted,
        String dateFrom,
        String dateTo,
        String description,
        String inspectionStatus,
        boolean isCommitted,
        String markOfOrigin,
        String recordType,
        String applicationInformation,
        String initials
) {

    /** Ports {@code ACCOUNTING_SEQUENCE_PROCESSED_FIELD_ORDER}. */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountingReason",
            "accountingSequenceId",
            "applicationInformation",
            "dateCommitted",
            "dateFrom",
            "dateTo",
            "description",
            "initials",
            "inspectionStatus",
            "isCommitted",
            "markOfOrigin",
            "recordType"
    );
}
