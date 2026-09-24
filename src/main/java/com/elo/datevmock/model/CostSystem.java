package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::CostSystem} (5 fields, already the complete
 * real shape — no trimming needed for SB3's scoping purposes).
 */
public record CostSystem(
        String id,
        String shortName,
        boolean isActivatedForPostings,
        int number,
        int costField
) {
}
