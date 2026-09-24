package com.elo.datevmock.model;

/**
 * Ports {@code app/models.py::Address} (`datev.address` --
 * creditor/debitor `addresses[]` item). Component declaration order below
 * is load-bearing: {@link com.elo.datevmock.xml.DatevXmlRenderer} renders
 * nested record fields via {@code getRecordComponents()} in this exact
 * order, matching the field order in the Python dataclass.
 */
public record Address(
        String id,
        AddressUsageType addressUsageType,
        String additionalCorrespondenceTitle,
        String additionalDeliveryText1,
        String additionalDeliveryText2,
        String addressAppendix,
        String addressManuallyEdited,
        String addressType,
        String city,
        String countryCode,
        String district,
        String individualShippingInformation,
        Boolean isAddressManuallyEdited,
        String note,
        String postOfficeBox,
        String postalCode,
        String street,
        String validFrom,
        String validTo
) {
}
