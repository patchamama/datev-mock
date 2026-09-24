package com.elo.datevmock.masterdata;

import com.elo.datevmock.model.ClientResource;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Ports {@code app/json_serializers.py::serialize_master_data_clients_json}:
 * a simplified 9-field JSON projection of {@link ClientResource}, not an
 * independent schema — {@code client_since}/{@code client_to} included only
 * when set.
 */
public final class MasterDataClientJson {

    private MasterDataClientJson() {
    }

    public static List<Map<String, Object>> project(List<ClientResource> records) {
        return records.stream().map(MasterDataClientJson::projectOne).toList();
    }

    private static Map<String, Object> projectOne(ClientResource record) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("id", record.id());
        putIfPresent(entry, "legal_person_id", record.legalPersonId());
        entry.put("name", record.name());
        entry.put("number", record.number());
        entry.put("status", record.status());
        entry.put("timestamp", record.timestamp());
        entry.put("type", record.type());
        putIfPresent(entry, "client_since", record.clientSince());
        putIfPresent(entry, "client_to", record.clientTo());
        return entry;
    }

    private static void putIfPresent(Map<String, Object> entry, String key, Object value) {
        if (value != null) {
            entry.put(key, value);
        }
    }
}
