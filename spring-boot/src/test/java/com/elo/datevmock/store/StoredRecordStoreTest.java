package com.elo.datevmock.store;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

/**
 * Ports {@code app/db.py} / {@code tests/test_db.py}: the generic
 * SQLite-backed CRUD core behind every write endpoint (SB5-SB7 will wire
 * controllers on top of this). One isolated SQLite file per test (JUnit
 * {@code @TempDir}), same isolation precedent as FastAPI's per-test
 * monkeypatched {@code DB_PATH}.
 */
class StoredRecordStoreTest {

    private StoredRecordStore newStore(Path tempDir) {
        return new StoredRecordStore(tempDir.resolve("datev_mock_test.db"));
    }

    @Test
    void initDbIsIdempotent(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        assertDoesNotThrow(store::initDb);
        assertDoesNotThrow(store::initDb);
    }

    @Test
    void upsertThenGetRecordRoundTrips(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        Map<String, Object> stored = store.upsertRecord(
                "accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"));
        assertEquals("Acme", stored.get("caption"));

        Optional<Map<String, Object>> fetched = store.getRecord("accounting.debitors", "d1");
        assertTrue(fetched.isPresent());
        assertEquals(Map.of("id", "d1", "caption", "Acme"), fetched.get());
    }

    @Test
    void getRecordReturnsEmptyWhenMissing(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        assertTrue(store.getRecord("accounting.debitors", "does-not-exist").isEmpty());
    }

    @Test
    void listRecordsReturnsEveryRowForAResourceType(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"));
        store.upsertRecord("accounting.debitors", "d2", Map.of("id", "d2", "caption", "Beta"));
        store.upsertRecord("accounting.creditors", "c1", Map.of("id", "c1", "caption", "Gamma"));

        List<Map<String, Object>> debitors = store.listRecords("accounting.debitors");
        assertEquals(Set.of("d1", "d2"), debitors.stream().map(r -> r.get("id")).collect(java.util.stream.Collectors.toSet()));

        List<Map<String, Object>> creditors = store.listRecords("accounting.creditors");
        assertEquals(Set.of("c1"), creditors.stream().map(r -> r.get("id")).collect(java.util.stream.Collectors.toSet()));
    }

    @Test
    void deleteRecordRemovesItAndReportsSuccess(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"));
        assertTrue(store.deleteRecord("accounting.debitors", "d1"));
        assertTrue(store.getRecord("accounting.debitors", "d1").isEmpty());
    }

    @Test
    void deleteRecordReturnsFalseForUnknownId(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        assertFalse(store.deleteRecord("accounting.debitors", "does-not-exist"));
    }

    @Test
    void resetClearsEveryResourceType(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1"));
        store.upsertRecord("accounting.creditors", "c1", Map.of("id", "c1"));
        store.reset();
        assertTrue(store.listRecords("accounting.debitors").isEmpty());
        assertTrue(store.listRecords("accounting.creditors").isEmpty());
    }

    @Test
    void upsertKeepsCreatedAtButChangesUpdatedAtOnSecondWrite(@TempDir Path tempDir) throws InterruptedException {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"));
        StoredRecordStore.RowMeta first = store.rowMeta("accounting.debitors", "d1").orElseThrow();

        Thread.sleep(10);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme Updated"));
        StoredRecordStore.RowMeta second = store.rowMeta("accounting.debitors", "d1").orElseThrow();

        assertEquals(first.createdAt(), second.createdAt());
        assertTrue(!second.updatedAt().equals(first.updatedAt()));
        assertEquals("Acme Updated", store.getRecord("accounting.debitors", "d1").orElseThrow().get("caption"));
    }

    @Test
    void listRecordsFiltersByClientIdAndFiscalYearId(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1"), "c-1", "fy-1");
        store.upsertRecord("accounting.debitors", "d2", Map.of("id", "d2"), "c-2", "fy-1");

        List<Map<String, Object>> filtered = store.listRecords("accounting.debitors", "c-1", null);
        assertEquals(Set.of("d1"), filtered.stream().map(r -> r.get("id")).collect(java.util.stream.Collectors.toSet()));
    }

    @Test
    void listAllWithMetaReturnsMetadataForAdminUi(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"), "c-1", null);
        List<StoredRecordStore.StoredRecordMeta> rows = store.listAllWithMeta();
        assertEquals(1, rows.size());
        StoredRecordStore.StoredRecordMeta row = rows.get(0);
        assertEquals("accounting.debitors", row.resourceType());
        assertEquals("d1", row.recordId());
        assertEquals("c-1", row.clientId());
        assertEquals(Map.of("id", "d1", "caption", "Acme"), row.data());
        assertTrue(row.createdAt() != null && row.updatedAt() != null);
    }

    @Test
    void deleteRecordsBulkRemovesMatchingRowsOnly(@TempDir Path tempDir) {
        StoredRecordStore store = newStore(tempDir);
        store.upsertRecord("master_data.client_responsibilities", "r1", Map.of("id", 1), "client-a", null);
        store.upsertRecord("master_data.client_responsibilities", "r2", Map.of("id", 2), "client-a", null);
        store.upsertRecord("master_data.client_responsibilities", "r3", Map.of("id", 3), "client-b", null);

        int deleted = store.deleteRecords("master_data.client_responsibilities", "client-a", null);

        assertEquals(2, deleted);
        List<Map<String, Object>> remaining = store.listRecords("master_data.client_responsibilities");
        assertEquals(Set.of(3), remaining.stream().map(r -> r.get("id")).collect(java.util.stream.Collectors.toSet()));
    }

    @Test
    void writtenRecordSurvivesASimulatedRestart(@TempDir Path tempDir) {
        Path dbFile = tempDir.resolve("restart.db");
        StoredRecordStore first = new StoredRecordStore(dbFile);
        first.upsertRecord("accounting.debitors", "d1", Map.of("id", "d1", "caption", "Acme"));

        // Simulate an app restart: a brand-new StoredRecordStore instance
        // pointed at the same file, with no shared in-memory state.
        StoredRecordStore afterRestart = new StoredRecordStore(dbFile);
        Optional<Map<String, Object>> fetched = afterRestart.getRecord("accounting.debitors", "d1");
        assertTrue(fetched.isPresent());
        assertEquals("Acme", fetched.get().get("caption"));
    }
}
