package com.elo.datevmock.model;

/** Ports {@code app/models.py::CommunicationUsageType}. */
public record CommunicationUsageType(
        boolean isMainCommunicationUsageType,
        boolean isMainManagementPhone
) {
}
