package com.elo.datevmock.model;

import java.util.List;
import java.util.Set;

/**
 * Ports {@code app/models.py::Creditor}. {@code accountingInformation}/
 * {@code legalPerson}/{@code naturalPerson}/{@code notSpecifiedPerson} stay
 * {@code Object}-typed (always null in this epic's fixtures) -- their real
 * nested shapes are out of SB2's representative-model scope (ported
 * domain-by-domain in SB5-SB8); this still exercises the same "arbitrary
 * nullable nested field" rendering path as a fully-typed one would.
 */
public record Creditor(
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

    /**
     * Shared field order for `Creditor`/`Debitor` XML -- ports
     * {@code app/models.py::BUSINESS_PARTNER_FIELD_ORDER} (Id/Parent/
     * membersToSerialize preamble, then every remaining field in
     * alphabetical PascalCase order).
     */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountNumber",
            "accountingInformation",
            "addresseeId",
            "addresses",
            "alternativeSearchName",
            "banks",
            "businessPartnerNumber",
            "businessPartnerRelationId",
            "caption",
            "communications",
            "complimentaryClose",
            "correspondenceTitle",
            "dateLastModification",
            "euVatIdCountryCode",
            "euVatIdNumber",
            "isBusinessPartnerActive",
            "isOrganizationBusinessPartner",
            "legalEntityType",
            "legalPerson",
            "naturalPerson",
            "notSpecifiedPerson",
            "salutation",
            "shortName",
            "thirdPartyNumber"
    );

    /**
     * Fields that carry the extra {@code xmlns:d3p1=".../Contracts.Common"}
     * namespace override when {@code i:nil="true"} -- ports
     * {@code BUSINESS_PARTNER_COMMON_NS_FIELDS}.
     */
    public static final Set<String> COMMON_NS_FIELDS = Set.of(
            "addresses", "banks", "communications", "legalPerson", "naturalPerson", "notSpecifiedPerson");
}
