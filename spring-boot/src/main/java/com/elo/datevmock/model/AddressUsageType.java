package com.elo.datevmock.model;

/** Ports {@code app/models.py::AddressUsageType} (`datev.address-usage-type`). */
public record AddressUsageType(
        boolean isCorrespondenceAddress,
        boolean isDefaultDeliveryAddress,
        boolean isDefaultPaymentAddress,
        boolean isDeliveryAddress,
        boolean isMainPostOfficeBoxAddress,
        boolean isMainStreetAddress,
        boolean isManagementAddress
) {
}
