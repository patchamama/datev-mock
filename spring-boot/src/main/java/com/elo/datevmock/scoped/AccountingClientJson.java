package com.elo.datevmock.scoped;

import com.elo.datevmock.model.AccountingClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Ports {@code app/json_serializers.py::serialize_clients_json}: a 4-field JSON projection of {@link AccountingClient}. */
public final class AccountingClientJson {

    private AccountingClientJson() {
    }

    public static List<Map<String, Object>> project(List<AccountingClient> records) {
        return records.stream().map(AccountingClientJson::projectOne).toList();
    }

    private static Map<String, Object> projectOne(AccountingClient record) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("id", record.id());
        entry.put("name", record.name());
        entry.put("number", record.number());
        entry.put("company_data", null);
        return entry;
    }
}
