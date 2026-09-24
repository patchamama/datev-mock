package com.elo.datevmock.xml;

import com.elo.datevmock.model.ClientResource;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_client_resources}. */
public final class ClientResourceXmlSerializer {

    private ClientResourceXmlSerializer() {
    }

    public static String serialize(List<ClientResource> records) {
        StringBuilder body = new StringBuilder();
        for (ClientResource record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    ClientResource.XML_FIELD_ORDER,
                    "ClientResource",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfClientResource", Namespaces.MASTER_DATA_NS, body.toString());
    }
}
