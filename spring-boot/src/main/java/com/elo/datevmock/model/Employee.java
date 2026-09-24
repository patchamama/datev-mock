package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::Employee} — {@code master-data/v1/employees}
 * (+ {@code /{id}}). No fake dataset exists for this resource in FastAPI
 * either ("no `fake_data.py` generator") — served purely from the write
 * overlay, same as here.
 */
public record Employee(
        String id,
        String name,
        String naturalPersonId,
        String displayName,
        String email,
        String entryDate,
        String fax,
        String initials,
        String note,
        Integer number,
        String phoneExtension,
        String separationDate,
        String status,
        String timestamp,
        String organizationId,
        String organizationName,
        String organizationNumber,
        String establishmentId,
        String establishmentName,
        String establishmentNumber,
        String establishmentShortName,
        String functionalAreaId,
        String functionalAreaName,
        String functionalAreaShortName
) {
}
