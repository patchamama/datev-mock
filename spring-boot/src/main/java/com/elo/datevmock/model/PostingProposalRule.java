package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::PostingProposalRule} -- shared shape for
 * incoming and outgoing invoices (identical contract, reused for both
 * directions).
 */
public record PostingProposalRule(
        String id,
        boolean uncertainLabel,
        AssignmentCriteria assignmentCriteria,
        List<PostingProposalInformation> postingProposalInformation,
        String creationDate,
        String lastUsedDate
) {

    /** Ports {@code POSTING_PROPOSAL_RULE_FIELD_ORDER}; nested fields excluded (JSON-only, no real XML evidence). */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "creationDate",
            "lastUsedDate",
            "uncertainLabel"
    );
}
