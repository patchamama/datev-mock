package com.elo.datevmock.xml;

import com.elo.datevmock.model.AccountingClient;

import java.util.List;

/** Ports {@code app/xml_serializers.py::serialize_clients} (accounting Client, not master-data ClientResource). */
public final class AccountingClientXmlSerializer {

    private AccountingClientXmlSerializer() {
    }

    public static String serialize(List<AccountingClient> records) {
        StringBuilder body = new StringBuilder();
        for (AccountingClient record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record, AccountingClient.XML_FIELD_ORDER, "Client",
                    AccountingClientXmlSerializer::nsAttr));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfClient", Namespaces.ACCOUNTING_CLIENTS_NS, body.toString());
    }

    /** Ports {@code _accounting_ns_attr}. */
    private static String nsAttr(String fieldName) {
        if (fieldName.equals("id") || fieldName.equals("parent")) {
            return " xmlns=\"" + Namespaces.SERVICEBUS_NS + "\"";
        }
        if (fieldName.equals("membersToSerialize")) {
            return " xmlns:d3p1=\"" + Namespaces.ARRAYS_NS + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\"";
        }
        if (fieldName.equals("accountingProductivities")) {
            return " xmlns:d3p1=\"" + Namespaces.ACCOUNTING_PRODUCTIVITIES_NS + "\"";
        }
        return "";
    }
}
