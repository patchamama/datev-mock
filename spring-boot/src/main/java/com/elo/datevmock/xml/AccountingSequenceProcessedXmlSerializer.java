package com.elo.datevmock.xml;

import com.elo.datevmock.model.AccountingSequenceProcessed;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_accounting_sequences_processed}. */
public final class AccountingSequenceProcessedXmlSerializer {

    private AccountingSequenceProcessedXmlSerializer() {
    }

    public static String serialize(List<AccountingSequenceProcessed> records) {
        StringBuilder body = new StringBuilder();
        for (AccountingSequenceProcessed record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    AccountingSequenceProcessed.XML_FIELD_ORDER,
                    "AccountingSequenceProcessed",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray(
                "ArrayOfAccountingSequenceProcessed",
                Namespaces.ACCOUNTING_SEQUENCE_PROCESSED_NS,
                body.toString());
    }
}
