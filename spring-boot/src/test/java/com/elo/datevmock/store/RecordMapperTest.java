package com.elo.datevmock.store;

import com.elo.datevmock.model.CostCenter;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports {@code app/db.py::record_to_dataclass}/{@code merge_with_stored}:
 * turning a stored (validated) record dict back into the typed record the
 * XML/JSON serializers expect, and unioning generated ("fake") records with
 * whatever's been written to SQLite for the same resource type -- SQLite
 * wins on a shared id (PUT-over-fake semantics), a new id is appended.
 */
class RecordMapperTest {

    private static Map<String, Object> fullCostCenterData() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", "cc-1");
        data.put("longName", "Cost Center One");
        data.put("shortName", "CC1");
        data.put("creationDate", "2026-01-01T00:00:00+01:00");
        data.put("costRates", null);
        data.put("properties", null);
        data.put("dateLastModification", "2026-01-01T00:00:00+01:00");
        data.put("email", "cc1@example.com");
        data.put("note", "note");
        data.put("postableFrom", "2026-01-01T00:00:00+01:00");
        data.put("postableTo", "2026-12-31T00:00:00+01:00");
        data.put("referenceValue", "ref");
        data.put("responsible", "someone");
        return data;
    }

    @Test
    void fromStoredBuildsARecordFromAFullDataMap() {
        CostCenter cc = RecordMapper.fromStored(CostCenter.class, fullCostCenterData(), Map.of(), Set.of());
        assertEquals("cc-1", cc.id());
        assertEquals("CC1", cc.shortName());
        assertEquals("someone", cc.responsible());
    }

    @Test
    void fromStoredUsesTypeAppropriateDefaultsForMissingRequiredFields() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", "cc-2");
        // every other field omitted -- Strings default to "", nullable/object fields to null.
        CostCenter cc = RecordMapper.fromStored(CostCenter.class, data, Map.of(), Set.of());
        assertEquals("cc-2", cc.id());
        assertEquals("", cc.longName());
        assertEquals("", cc.shortName());
        assertNull(cc.costRates());
    }

    @Test
    void fromStoredForcesNilFieldsToNullRegardlessOfStoredValue() {
        Map<String, Object> data = fullCostCenterData();
        CostCenter cc = RecordMapper.fromStored(CostCenter.class, data, Map.of(), Set.of("note", "email"));
        assertNull(cc.note());
        assertNull(cc.email());
        assertEquals("cc-1", cc.id());
    }

    @Test
    void fromStoredTranslatesASourceKeyViaFieldMap() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("id", "cc-3");
        data.put("short_name", "SNAKE"); // stored under a snake_case source key
        CostCenter cc = RecordMapper.fromStored(
                CostCenter.class, data, Map.of("short_name", "shortName"), Set.of());
        assertEquals("SNAKE", cc.shortName());
    }

    @Test
    void mergeWithStoredReplacesAFakeRecordSharingAnIdAndAppendsNewOnes(@TempDir Path tempDir) {
        StoredRecordStore store = new StoredRecordStore(tempDir.resolve("merge.db"));
        CostCenter fake1 = new CostCenter("cc-1", "Fake One", "F1", null, null, null, null, null, null, null, null, null, null);
        CostCenter fake2 = new CostCenter("cc-2", "Fake Two", "F2", null, null, null, null, null, null, null, null, null, null);

        Map<String, Object> overwrite = new LinkedHashMap<>();
        overwrite.put("id", "cc-1");
        overwrite.put("longName", "Overwritten One");
        overwrite.put("shortName", "O1");
        store.upsertRecord("accounting.cost_centers", "cc-1", overwrite);

        Map<String, Object> brandNew = new LinkedHashMap<>();
        brandNew.put("id", "cc-9");
        brandNew.put("longName", "Brand New");
        brandNew.put("shortName", "BN");
        store.upsertRecord("accounting.cost_centers", "cc-9", brandNew);

        List<CostCenter> merged = RecordMapper.mergeWithStored(
                List.of(fake1, fake2), "accounting.cost_centers", CostCenter.class, "id",
                Map.of(), Set.of(), store, null, null);

        Map<String, CostCenter> byId = new LinkedHashMap<>();
        merged.forEach(cc -> byId.put(cc.id(), cc));

        assertEquals(3, merged.size());
        assertEquals("Overwritten One", byId.get("cc-1").longName());
        assertEquals("Fake Two", byId.get("cc-2").longName());
        assertEquals("Brand New", byId.get("cc-9").longName());
    }

    @Test
    void mergeWithStoredReturnsFakeRecordsUnchangedWhenNothingIsStored(@TempDir Path tempDir) {
        StoredRecordStore store = new StoredRecordStore(tempDir.resolve("merge-empty.db"));
        CostCenter fake1 = new CostCenter("cc-1", "Fake One", "F1", null, null, null, null, null, null, null, null, null, null);

        List<CostCenter> merged = RecordMapper.mergeWithStored(
                List.of(fake1), "accounting.cost_centers", CostCenter.class, "id",
                Map.of(), Set.of(), store, null, null);

        assertEquals(1, merged.size());
        assertTrue(merged.contains(fake1));
    }
}
