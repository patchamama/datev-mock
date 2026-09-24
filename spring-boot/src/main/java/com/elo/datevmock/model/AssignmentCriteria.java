package com.elo.datevmock.model;

/** Ports {@code app/models.py::AssignmentCriteria} (JSON-only, nested under {@link PostingProposalRule}). */
public record AssignmentCriteria(
        String name,
        double taxRate,
        String goodsAndServices
) {
}
