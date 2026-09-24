package com.elo.datevmock.xml;

import com.elo.datevmock.model.AccountingTransactionKey;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_accounting_transaction_keys}. */
public final class AccountingTransactionKeyXmlSerializer {

    private AccountingTransactionKeyXmlSerializer() {
    }

    public static String serialize(List<AccountingTransactionKey> records) {
        StringBuilder body = new StringBuilder();
        for (AccountingTransactionKey record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    AccountingTransactionKey.XML_FIELD_ORDER,
                    "AccountingTransactionKey",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray(
                "ArrayOfAccountingTransactionKey", Namespaces.ACCOUNTING_TRANSACTION_KEY_NS, body.toString());
    }
}
