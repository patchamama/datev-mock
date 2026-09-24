package com.elo.datevmock.xml;

import com.elo.datevmock.model.FiscalYear;

import java.util.List;
import java.util.Set;

/**
 * Ports {@code app/xml_serializers.py::serialize_fiscal_years}. Renders the
 * trimmed {@link FiscalYear#XML_FIELD_ORDER} -- see that record's javadoc
 * for the documented SB6 field-completeness gap.
 */
public final class FiscalYearXmlSerializer {

    private FiscalYearXmlSerializer() {
    }

    public static String serialize(List<FiscalYear> records) {
        StringBuilder body = new StringBuilder();
        for (FiscalYear record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    FiscalYear.XML_FIELD_ORDER,
                    "FiscalYear",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfFiscalYear", Namespaces.FISCAL_YEAR_NS, body.toString());
    }
}
