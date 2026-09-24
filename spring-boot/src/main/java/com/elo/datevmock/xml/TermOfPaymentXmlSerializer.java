package com.elo.datevmock.xml;

import com.elo.datevmock.model.TermOfPayment;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_terms_of_payment}. */
public final class TermOfPaymentXmlSerializer {

    private TermOfPaymentXmlSerializer() {
    }

    public static String serialize(List<TermOfPayment> records) {
        StringBuilder body = new StringBuilder();
        for (TermOfPayment record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    TermOfPayment.XML_FIELD_ORDER,
                    "TermOfPayment",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfTermOfPayment", Namespaces.TERM_OF_PAYMENT_NS, body.toString());
    }
}
