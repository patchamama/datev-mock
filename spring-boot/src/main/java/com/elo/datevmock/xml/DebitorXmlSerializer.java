package com.elo.datevmock.xml;

import com.elo.datevmock.model.Debitor;

import java.util.List;

/** Ports {@code app/xml_serializers.py::serialize_debitors}. */
public final class DebitorXmlSerializer {

    private DebitorXmlSerializer() {
    }

    public static String serialize(List<Debitor> records) {
        StringBuilder body = new StringBuilder();
        for (Debitor record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    Debitor.XML_FIELD_ORDER,
                    "Debitor",
                    DatevXmlRenderer.genericNsAttrResolver(
                            Debitor.COMMON_NS_FIELDS, Namespaces.ACCOUNTING_COMMON_NS)));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfDebitor", Namespaces.BUSINESS_PARTNERS_NS, body.toString());
    }
}
