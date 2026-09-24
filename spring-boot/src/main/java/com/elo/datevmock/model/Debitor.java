package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::Debitor} -- structurally identical to
 * {@link Creditor} (shares {@code BUSINESS_PARTNER_FIELD_ORDER}/
 * {@code BUSINESS_PARTNER_COMMON_NS_FIELDS} in the Python source), so this
 * mirrors {@link Creditor}'s own field list and XML metadata field for
 * field rather than sharing a type (Java records can't extend one another).
 */
public record Debitor(
        String id,
        int accountNumber,
        String addresseeId,
        String businessPartnerNumber,
        String businessPartnerRelationId,
        String caption,
        String dateLastModification,
        boolean isBusinessPartnerActive,
        boolean isOrganizationBusinessPartner,
        String legalEntityType,
        String shortName,
        Object accountingInformation,
        List<Address> addresses,
        String alternativeSearchName,
        List<BusinessPartnerBank> banks,
        List<Communication> communications,
        String complimentaryClose,
        String correspondenceTitle,
        String euVatIdCountryCode,
        String euVatIdNumber,
        Object legalPerson,
        Object naturalPerson,
        Object notSpecifiedPerson,
        String salutation,
        String thirdPartyNumber
) {

    public static final List<String> XML_FIELD_ORDER = Creditor.XML_FIELD_ORDER;
    public static final java.util.Set<String> COMMON_NS_FIELDS = Creditor.COMMON_NS_FIELDS;
}
