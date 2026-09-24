package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::HistoricalValue} — one entry of an
 * {@link Addressee} "historical field" array
 * ({@code companyNames}/{@code shortNames}/{@code legalFormIds}/{@code surnames}).
 */
public record HistoricalValue(String value, String validFrom) {
}
