package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::Addressee} — flat top-level fields only (no
 * {@code expand} support, matching the FastAPI mock's own scope). JSON-only,
 * snake_case, via {@link com.elo.datevmock.json.DatevJsonMapper}.
 */
public record Addressee(
        String id,
        String type,
        String status,
        String timestamp,
        String euVatIdCountryCode,
        String euVatIdNumber,
        String currentShortName,
        List<HistoricalValue> shortNames,
        String surrogateName,
        // natural_person-only (by convention, not schema-enforced)
        String dateOfBirth,
        String etin,
        String firstname,
        String sex,
        String currentSurname,
        List<HistoricalValue> surnames,
        String taxIdentificationNumber,
        // legal_person-only (by convention, not schema-enforced)
        String currentCompanyName,
        List<HistoricalValue> companyNames,
        String dateOfFoundation,
        String currentLegalFormId,
        List<HistoricalValue> legalFormIds
) {
}
