package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::CostRate}. {@code validFrom}/{@code validTo}
 * are genuinely integer-encoded dates (e.g. {@code 20161201}), not
 * date-time strings -- an explicit DATEV spec quirk, not a typo.
 */
public record CostRate(int validFrom, int validTo, double rate) {
}
