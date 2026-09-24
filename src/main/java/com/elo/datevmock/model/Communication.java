package com.elo.datevmock.model;

/** Ports {@code app/models.py::Communication} (`datev.communication`). */
public record Communication(
        String id,
        String communicationDataContent,
        String communicationType,
        String note,
        CommunicationUsageType communicationUsageType
) {
}
