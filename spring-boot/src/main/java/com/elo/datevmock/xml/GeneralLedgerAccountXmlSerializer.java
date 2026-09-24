package com.elo.datevmock.xml;

import com.elo.datevmock.model.GeneralLedgerAccount;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_general_ledger_accounts}. */
public final class GeneralLedgerAccountXmlSerializer {

    private GeneralLedgerAccountXmlSerializer() {
    }

    public static String serialize(List<GeneralLedgerAccount> records) {
        StringBuilder body = new StringBuilder();
        for (GeneralLedgerAccount record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    GeneralLedgerAccount.XML_FIELD_ORDER,
                    "GeneralLedgerAccount",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray(
                "ArrayOfGeneralLedgerAccount", Namespaces.GENERAL_LEDGER_ACCOUNT_NS, body.toString());
    }
}
