package com.elo.datevmock.xml;

import com.elo.datevmock.model.OpenItem;

import java.util.List;
import java.util.Set;

/**
 * Ports {@code app/xml_serializers.py::serialize_open_items} -- shared
 * serializer for accounts-payable, accounts-payable/condense, and
 * accounts-receivable/condense (identical {@code OpenItem} shape).
 */
public final class OpenItemXmlSerializer {

    private OpenItemXmlSerializer() {
    }

    public static String serialize(List<OpenItem> records) {
        StringBuilder body = new StringBuilder();
        for (OpenItem record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    OpenItem.XML_FIELD_ORDER,
                    "OpenItem",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfOpenItem", Namespaces.OPEN_ITEM_NS, body.toString());
    }
}
