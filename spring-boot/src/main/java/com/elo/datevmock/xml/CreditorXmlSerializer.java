package com.elo.datevmock.xml;

import com.elo.datevmock.model.Creditor;

import java.util.List;

/** Ports {@code app/xml_serializers.py::serialize_creditors}. */
public final class CreditorXmlSerializer {

    private CreditorXmlSerializer() {
    }

    public static String serialize(List<Creditor> records) {
        StringBuilder body = new StringBuilder();
        for (Creditor record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    Creditor.XML_FIELD_ORDER,
                    "Creditor",
                    DatevXmlRenderer.genericNsAttrResolver(
                            Creditor.COMMON_NS_FIELDS, Namespaces.ACCOUNTING_COMMON_NS)));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfCreditor", Namespaces.BUSINESS_PARTNERS_NS, body.toString());
    }
}
