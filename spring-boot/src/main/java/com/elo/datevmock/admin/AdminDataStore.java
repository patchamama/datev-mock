package com.elo.datevmock.admin;

import com.elo.datevmock.masterdata.MasterDataGenerator;
import com.elo.datevmock.model.AccountingClient;
import com.elo.datevmock.model.ClientResource;
import com.elo.datevmock.scoped.AccountingClientGenerator;
import com.elo.datevmock.store.RecordMapper;
import com.elo.datevmock.store.StoredRecordStore;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * Ports {@code app/data_store.py}'s master-data/accounting-client CRUD+reset
 * for the admin panel's editable tables.
 *
 * <p><b>SB12 retrofit</b> (closes the honest gap this class's javadoc used to
 * document, found reading {@code app/data_store.py} in full for SB9): this
 * store no longer keeps its own independent {@code CopyOnWriteArrayList} for
 * either resource. Both are backed by the exact same {@link StoredRecordStore}
 * rows -- {@code "master_data.clients"} / {@code "accounting.clients"} -- that
 * SB5's {@code MasterDataController} and SB6's {@code AccountingController}
 * already merge over the same fixed fake datasets ({@link MasterDataGenerator}
 * / {@link AccountingClientGenerator}) those controllers read on their public
 * GET routes. An admin create/update/delete is now visible on the matching
 * public GET route immediately (no restart), and a public write via SB5's own
 * {@code POST}/{@code PUT} on {@code /datev/api/master-data/v1/clients} is
 * visible on the admin read the same way -- both sides read/write one shared
 * bean instead of two independent copies.
 *
 * <p><b>One known limitation carried by this design</b>: deleting a record
 * that only ever existed as generator/"fake" data (never written to either
 * endpoint) has no stored row for {@link StoredRecordStore#deleteRecord} to
 * remove. That case is represented as an explicit tombstone row instead of a
 * true row removal -- see {@link RecordMapper#DELETED_MARKER_KEY} and
 * {@link RecordMapper#mergeWithStored}, which excludes any id carrying that
 * marker from the merged result on every subsequent read.
 */
@Component
public class AdminDataStore {

    static final String MASTER_DATA_CLIENTS_RESOURCE = "master_data.clients";
    static final String ACCOUNTING_CLIENTS_RESOURCE = "accounting.clients";

    private final MasterDataGenerator masterDataGenerator;
    private final AccountingClientGenerator accountingClientGenerator;
    private final StoredRecordStore store;

    public AdminDataStore(
            MasterDataGenerator masterDataGenerator,
            AccountingClientGenerator accountingClientGenerator,
            StoredRecordStore store) {
        this.masterDataGenerator = masterDataGenerator;
        this.accountingClientGenerator = accountingClientGenerator;
        this.store = store;
    }

    /**
     * Clears every write overlay (and tombstone) for both admin-managed
     * resources, restoring the pure generated baseline -- matches
     * {@code app/data_store.py::reset()}'s cardinality-restoring contract,
     * now expressed as "no overrides left" rather than "regenerate a second
     * in-memory copy".
     */
    public void reset() {
        store.deleteRecords(MASTER_DATA_CLIENTS_RESOURCE, null, null);
        store.deleteRecords(ACCOUNTING_CLIENTS_RESOURCE, null, null);
    }

    // --- master data ---

    public List<ClientResource> listMasterData() {
        return mergedMasterData();
    }

    public ClientResource addMasterData(Map<String, Object> fields) {
        Map<String, Object> camel = toCamelKeys(fields);
        camel.put("id", UUID.randomUUID().toString());
        ClientResource record = RecordMapper.fromStored(ClientResource.class, camel, Map.of(), Set.of());
        persistMasterData(record);
        return record;
    }

    public ClientResource updateMasterData(String id, Map<String, Object> fields) {
        ClientResource current = findMasterData(id).orElseThrow(() -> new NoSuchElementException(id));
        ClientResource updated = RecordPatcher.patch(current, fields);
        persistMasterData(updated);
        return updated;
    }

    public void deleteMasterData(String id) {
        deleteWithTombstone(MASTER_DATA_CLIENTS_RESOURCE, id);
    }

    private List<ClientResource> mergedMasterData() {
        return RecordMapper.mergeWithStored(
                masterDataGenerator.clientResources(), MASTER_DATA_CLIENTS_RESOURCE, ClientResource.class,
                "id", Map.of(), Set.of(), store, null, null);
    }

    private Optional<ClientResource> findMasterData(String id) {
        return mergedMasterData().stream().filter(r -> r.id().equals(id)).findFirst();
    }

    private void persistMasterData(ClientResource record) {
        store.upsertRecord(MASTER_DATA_CLIENTS_RESOURCE, record.id(), RecordMapper.toSnakeCaseMap(record));
    }

    // --- accounting clients ---

    public List<AccountingClient> listAccountingClients() {
        return mergedAccountingClients();
    }

    public AccountingClient addAccountingClient(Map<String, Object> fields) {
        Map<String, Object> camel = toCamelKeys(fields);
        String freshId = UUID.randomUUID().toString();
        camel.put("id", freshId);
        camel.put("clientGuid", freshId);
        AccountingClient record = RecordMapper.fromStored(AccountingClient.class, camel, Map.of(), Set.of());
        persistAccountingClient(record);
        return record;
    }

    public AccountingClient updateAccountingClient(String id, Map<String, Object> fields) {
        AccountingClient current = findAccountingClient(id).orElseThrow(() -> new NoSuchElementException(id));
        AccountingClient updated = RecordPatcher.patch(current, fields);
        persistAccountingClient(updated);
        return updated;
    }

    public void deleteAccountingClient(String id) {
        deleteWithTombstone(ACCOUNTING_CLIENTS_RESOURCE, id);
    }

    private List<AccountingClient> mergedAccountingClients() {
        return RecordMapper.mergeWithStored(
                accountingClientGenerator.clients(), ACCOUNTING_CLIENTS_RESOURCE, AccountingClient.class,
                "id", Map.of(), Set.of(), store, null, null);
    }

    private Optional<AccountingClient> findAccountingClient(String id) {
        return mergedAccountingClients().stream().filter(r -> r.id().equals(id)).findFirst();
    }

    private void persistAccountingClient(AccountingClient record) {
        store.upsertRecord(ACCOUNTING_CLIENTS_RESOURCE, record.id(), RecordMapper.toSnakeCaseMap(record));
    }

    // --- shared helpers ---

    /**
     * Removes a real stored row when one exists (an admin- or publicly-
     * written record); otherwise the id is a generator-origin/"fake" record
     * with no row to remove, so a tombstone is written instead (see the
     * class javadoc's "known limitation" note).
     */
    private void deleteWithTombstone(String resourceType, String id) {
        boolean removed = store.deleteRecord(resourceType, id);
        if (!removed) {
            store.upsertRecord(resourceType, id, Map.of(RecordMapper.DELETED_MARKER_KEY, true, "id", id));
        }
    }

    private static Map<String, Object> toCamelKeys(Map<String, Object> fields) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : fields.entrySet()) {
            String key = entry.getKey();
            String camel = key.isEmpty() ? key : Character.toLowerCase(key.charAt(0)) + key.substring(1);
            result.put(camel, entry.getValue());
        }
        return result;
    }
}
