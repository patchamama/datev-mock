package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::Client} (the ACCOUNTING {@code GET .../clients}
 * shape -- 8-field XML layout with already-PascalCase-style field names in
 * the Python source, distinct from master-data's {@link ClientResource}).
 */
public record AccountingClient(
        String id,
        String clientGuid,
        String name,
        int number,
        String parent,
        String membersToSerialize,
        String accountingProductivities,
        String companyData
) {

    /** Ports {@code CLIENT_FIELD_ORDER}. */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountingProductivities",
            "clientGuid",
            "companyData",
            "name",
            "number"
    );
}
