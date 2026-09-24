package com.elo.datevmock.model;

import java.util.List;
import java.util.Map;

/**
 * Ports {@code app/models.py::CostCenter}. {@code costRates}/{@code properties}
 * are deliberately excluded from {@link #XML_FIELD_ORDER}: there is zero real
 * evidence these array fields exist in the XML contract (only in JSON), so
 * inventing a nested XML shape for them would be pure guesswork -- same
 * precedent as the FastAPI side.
 */
public record CostCenter(
        String id,
        String longName,
        String shortName,
        String creationDate,
        List<CostRate> costRates,
        List<Map<String, Object>> properties,
        String dateLastModification,
        String email,
        String note,
        String postableFrom,
        String postableTo,
        String referenceValue,
        String responsible
) {

    /**
     * `Id`/`Parent`/`membersToSerialize` preamble, then the remaining
     * *scalar* fields in alphabetical PascalCase order -- ports
     * {@code app/models.py::COST_CENTER_FIELD_ORDER} exactly.
     */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "creationDate",
            "dateLastModification",
            "email",
            "longName",
            "note",
            "postableFrom",
            "postableTo",
            "referenceValue",
            "responsible",
            "shortName"
    );

    /**
     * Returns a copy with {@code costRates} cleared to {@code null} --
     * ports {@code dataclasses.replace(record, cost_rates=None)} from
     * {@code app/routers/accounting.py::get_cost_centers}'s "legacy"
     * {@code datev_api_version} gate (matches ELO's older reference mock,
     * `serve-0.1-generate.jar`, which never sent this field at all).
     */
    public CostCenter withoutCostRates() {
        return new CostCenter(
                id, longName, shortName, creationDate, null, properties,
                dateLastModification, email, note, postableFrom, postableTo,
                referenceValue, responsible);
    }
}
