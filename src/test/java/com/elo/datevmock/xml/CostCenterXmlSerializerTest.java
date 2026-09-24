package com.elo.datevmock.xml;

import com.elo.datevmock.model.CostCenter;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * Golden-fixture test for {@code CostCenter} XML, ported from
 * {@code app/xml_serializers.py::serialize_cost_centers} and
 * {@code COST_CENTER_FIELD_ORDER}. {@code costRates}/{@code properties} are
 * excluded from the XML shape entirely (JSON-only, per the FastAPI
 * source's own comment) -- this must hold regardless of the
 * legacy/modern `datev_api_version` toggle, which only affects JSON.
 */
class CostCenterXmlSerializerTest {

    private static CostCenter sample() {
        return new CostCenter(
                "1", "Verwaltung", "VW", "2020-01-01T00:00:00.000+01:00",
                List.of(new com.elo.datevmock.model.CostRate(20161201, 20991231, 1.5)),
                List.of(),
                null, null, null, null, null, null, null);
    }

    @Test
    void rendersRequiredAndNilOptionalFieldsInDeclaredOrderWithServiceBusPreamble() {
        String xml = CostCenterXmlSerializer.serialize(List.of(sample()));
        String expected = Namespaces.XML_DECLARATION
                + "<ArrayOfCostCenter xmlns:i=\"" + Namespaces.XSI_NS
                + "\" xmlns=\"" + Namespaces.COST_CENTER_NS + "\">"
                + "<CostCenter>"
                + "<Id xmlns=\"" + Namespaces.SERVICEBUS_NS + "\">1</Id>"
                + "<Parent xmlns=\"" + Namespaces.SERVICEBUS_NS + "\" i:nil=\"true\"/>"
                + "<membersToSerialize xmlns:d3p1=\"" + Namespaces.ARRAYS_NS
                + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\" i:nil=\"true\"/>"
                + "<CreationDate>2020-01-01T00:00:00.000+01:00</CreationDate>"
                + "<DateLastModification i:nil=\"true\"/>"
                + "<Email i:nil=\"true\"/>"
                + "<LongName>Verwaltung</LongName>"
                + "<Note i:nil=\"true\"/>"
                + "<PostableFrom i:nil=\"true\"/>"
                + "<PostableTo i:nil=\"true\"/>"
                + "<ReferenceValue i:nil=\"true\"/>"
                + "<Responsible i:nil=\"true\"/>"
                + "<ShortName>VW</ShortName>"
                + "</CostCenter>"
                + "</ArrayOfCostCenter>";
        assertEquals(expected, xml);
    }

    @Test
    void neverRendersCostRatesOrPropertiesInXmlEvenWhenPopulated() {
        String xml = CostCenterXmlSerializer.serialize(List.of(sample()));
        assertFalse(xml.contains("CostRate"));
        assertFalse(xml.contains("Properties"));
    }
}
