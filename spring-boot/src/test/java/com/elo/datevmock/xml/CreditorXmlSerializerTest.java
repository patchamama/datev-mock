package com.elo.datevmock.xml;

import com.elo.datevmock.model.Address;
import com.elo.datevmock.model.AddressUsageType;
import com.elo.datevmock.model.Creditor;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Golden-fixture test ported from {@code app/xml_serializers.py::serialize_creditors}
 * / {@code BUSINESS_PARTNER_FIELD_ORDER} / {@code BUSINESS_PARTNER_COMMON_NS_FIELDS}.
 * Exercises the edge cases SB2's acceptance criteria call out: a nested
 * list-of-objects field ({@code addresses}, itself containing a nested
 * single-object field {@code addressUsageType}), a nil field with the extra
 * `d3p1` common namespace ({@code banks}/{@code communications}/
 * {@code legalPerson}/...), and a plain nil scalar (no extra namespace).
 */
class CreditorXmlSerializerTest {

    private static Creditor sample() {
        Address address = new Address(
                "addr1",
                new AddressUsageType(true, false, false, false, false, false, false),
                null, null, null, null, null, null, null, null, null, null, null,
                null, null, null, null, null, null);
        return new Creditor(
                "c1", 42, "a1", "bp1", "bpr1", "ACME",
                "2020-01-01T00:00:00.000+01:00", true, false, "1", "ACME",
                null, List.of(address), null, null, null, null, null, null, null,
                null, null, null, null, null);
    }

    @Test
    void rendersNestedListNestedObjectAndCommonNsNilFieldsCorrectly() {
        String xml = CreditorXmlSerializer.serialize(List.of(sample()));

        String commonNs = Namespaces.ACCOUNTING_COMMON_NS;
        String expectedAddress =
                "<Id>addr1</Id>"
                        + "<AddressUsageType>"
                        + "<IsCorrespondenceAddress>true</IsCorrespondenceAddress>"
                        + "<IsDefaultDeliveryAddress>false</IsDefaultDeliveryAddress>"
                        + "<IsDefaultPaymentAddress>false</IsDefaultPaymentAddress>"
                        + "<IsDeliveryAddress>false</IsDeliveryAddress>"
                        + "<IsMainPostOfficeBoxAddress>false</IsMainPostOfficeBoxAddress>"
                        + "<IsMainStreetAddress>false</IsMainStreetAddress>"
                        + "<IsManagementAddress>false</IsManagementAddress>"
                        + "</AddressUsageType>"
                        + "<AdditionalCorrespondenceTitle i:nil=\"true\"/>"
                        + "<AdditionalDeliveryText1 i:nil=\"true\"/>"
                        + "<AdditionalDeliveryText2 i:nil=\"true\"/>"
                        + "<AddressAppendix i:nil=\"true\"/>"
                        + "<AddressManuallyEdited i:nil=\"true\"/>"
                        + "<AddressType i:nil=\"true\"/>"
                        + "<City i:nil=\"true\"/>"
                        + "<CountryCode i:nil=\"true\"/>"
                        + "<District i:nil=\"true\"/>"
                        + "<IndividualShippingInformation i:nil=\"true\"/>"
                        + "<IsAddressManuallyEdited i:nil=\"true\"/>"
                        + "<Note i:nil=\"true\"/>"
                        + "<PostOfficeBox i:nil=\"true\"/>"
                        + "<PostalCode i:nil=\"true\"/>"
                        + "<Street i:nil=\"true\"/>"
                        + "<ValidFrom i:nil=\"true\"/>"
                        + "<ValidTo i:nil=\"true\"/>";

        String expectedCreditor =
                "<Id xmlns=\"" + Namespaces.SERVICEBUS_NS + "\">c1</Id>"
                        + "<Parent xmlns=\"" + Namespaces.SERVICEBUS_NS + "\" i:nil=\"true\"/>"
                        + "<membersToSerialize xmlns:d3p1=\"" + Namespaces.ARRAYS_NS
                        + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\" i:nil=\"true\"/>"
                        + "<AccountNumber>42</AccountNumber>"
                        + "<AccountingInformation i:nil=\"true\"/>"
                        + "<AddresseeId>a1</AddresseeId>"
                        + "<Addresses xmlns:d3p1=\"" + commonNs + "\"><Address>" + expectedAddress + "</Address></Addresses>"
                        + "<AlternativeSearchName i:nil=\"true\"/>"
                        + "<Banks xmlns:d3p1=\"" + commonNs + "\" i:nil=\"true\"/>"
                        + "<BusinessPartnerNumber>bp1</BusinessPartnerNumber>"
                        + "<BusinessPartnerRelationId>bpr1</BusinessPartnerRelationId>"
                        + "<Caption>ACME</Caption>"
                        + "<Communications xmlns:d3p1=\"" + commonNs + "\" i:nil=\"true\"/>"
                        + "<ComplimentaryClose i:nil=\"true\"/>"
                        + "<CorrespondenceTitle i:nil=\"true\"/>"
                        + "<DateLastModification>2020-01-01T00:00:00.000+01:00</DateLastModification>"
                        + "<EuVatIdCountryCode i:nil=\"true\"/>"
                        + "<EuVatIdNumber i:nil=\"true\"/>"
                        + "<IsBusinessPartnerActive>true</IsBusinessPartnerActive>"
                        + "<IsOrganizationBusinessPartner>false</IsOrganizationBusinessPartner>"
                        + "<LegalEntityType>1</LegalEntityType>"
                        + "<LegalPerson xmlns:d3p1=\"" + commonNs + "\" i:nil=\"true\"/>"
                        + "<NaturalPerson xmlns:d3p1=\"" + commonNs + "\" i:nil=\"true\"/>"
                        + "<NotSpecifiedPerson xmlns:d3p1=\"" + commonNs + "\" i:nil=\"true\"/>"
                        + "<Salutation i:nil=\"true\"/>"
                        + "<ShortName>ACME</ShortName>"
                        + "<ThirdPartyNumber i:nil=\"true\"/>";

        String expected = Namespaces.XML_DECLARATION
                + "<ArrayOfCreditor xmlns:i=\"" + Namespaces.XSI_NS
                + "\" xmlns=\"" + Namespaces.BUSINESS_PARTNERS_NS + "\">"
                + "<Creditor>" + expectedCreditor + "</Creditor>"
                + "</ArrayOfCreditor>";

        assertEquals(expected, xml);
    }
}
