package com.elo.datevmock.xml;

import com.elo.datevmock.model.Echo;

/**
 * Ports {@code app/xml_serializers.py::serialize_echo} 1:1: a small, flat,
 * dedicated serializer outside the generic {@link DatevXmlRenderer} engine
 * (Echo has no DataContractSerializer preamble fields like {@code
 * parent}/{@code membersToSerialize}, unlike the generic ServiceBus-family
 * contracts), matching the FastAPI source's own choice to keep this as a
 * standalone function rather than routing it through the generic renderer.
 */
public final class EchoXmlSerializer {

    private EchoXmlSerializer() {
    }

    public static String serialize(Echo echo) {
        return Namespaces.XML_DECLARATION
                + "<Echo xmlns:i=\"" + Namespaces.XSI_NS + "\" xmlns=\"" + Namespaces.ECHO_NS + "\">"
                + "<echo_message>" + escape(echo.echoMessage()) + "</echo_message>"
                + "<id>" + escape(echo.id()) + "</id>"
                + "</Echo>";
    }

    private static String escape(String text) {
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
