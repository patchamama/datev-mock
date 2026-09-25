package com.elo.datevmock.admin;

import com.elo.datevmock.masterdata.MasterDataGenerator;
import com.elo.datevmock.model.AccountingClient;
import com.elo.datevmock.model.ClientResource;
import com.elo.datevmock.scoped.AccountingClientGenerator;
import com.elo.datevmock.store.RecordMapper;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Ports {@code app/data_store.py}'s master-data/accounting-client
 * CRUD+reset for the admin panel's editable tables.
 *
 * <p><b>Honest gap</b> (found reading {@code app/data_store.py} in full for
 * SB9): in real FastAPI, this IS the exact same in-memory list the public
 * {@code GET /datev/api/master-data/v1/clients} and
 * {@code GET /datev/api/accounting/v1/clients} endpoints read from -- an
 * admin edit is visible on the real API immediately, with no separate
 * store. SB5's {@code MasterDataController}/SB6's {@code AccountingController}
 * were built against their own independent deterministic generators
 * instead (reasonably, given neither epic's own scope mentioned this
 * shared-store requirement), so in this Java port admin-panel edits here
 * do NOT currently flow through to those real public endpoints. This store
 * ports the CRUD/reset *shape* faithfully; wiring it as the literal shared
 * backing store for SB5/SB6's read endpoints is a retrofit left to SB10
 * (contract-parity verification), the same way SB7 retrofitted SB4's
 * SQLite overlay into SB6's GETs.
 */
@Component
public class AdminDataStore {

    private final MasterDataGenerator masterDataGenerator;
    private final AccountingClientGenerator accountingClientGenerator;
    private final List<ClientResource> masterData = new CopyOnWriteArrayList<>();
    private final List<AccountingClient> accountingClients = new CopyOnWriteArrayList<>();

    public AdminDataStore(MasterDataGenerator masterDataGenerator, AccountingClientGenerator accountingClientGenerator) {
        this.masterDataGenerator = masterDataGenerator;
        this.accountingClientGenerator = accountingClientGenerator;
        reset();
    }

    public synchronized void reset() {
        masterData.clear();
        masterData.addAll(masterDataGenerator.clientResources());
        accountingClients.clear();
        accountingClients.addAll(accountingClientGenerator.clients());
    }

    public List<ClientResource> listMasterData() {
        return List.copyOf(masterData);
    }

    public ClientResource addMasterData(Map<String, Object> fields) {
        Map<String, Object> camel = toCamelKeys(fields);
        camel.put("id", UUID.randomUUID().toString());
        ClientResource record = RecordMapper.fromStored(ClientResource.class, camel, Map.of(), Set.of());
        masterData.add(record);
        return record;
    }

    public ClientResource updateMasterData(String id, Map<String, Object> fields) {
        for (int i = 0; i < masterData.size(); i++) {
            if (masterData.get(i).id().equals(id)) {
                ClientResource updated = RecordPatcher.patch(masterData.get(i), fields);
                masterData.set(i, updated);
                return updated;
            }
        }
        throw new NoSuchElementException(id);
    }

    public void deleteMasterData(String id) {
        masterData.removeIf(r -> r.id().equals(id));
    }

    public List<AccountingClient> listAccountingClients() {
        return List.copyOf(accountingClients);
    }

    public AccountingClient addAccountingClient(Map<String, Object> fields) {
        Map<String, Object> camel = toCamelKeys(fields);
        String freshId = UUID.randomUUID().toString();
        camel.put("id", freshId);
        camel.put("clientGuid", freshId);
        AccountingClient record = RecordMapper.fromStored(AccountingClient.class, camel, Map.of(), Set.of());
        accountingClients.add(record);
        return record;
    }

    public AccountingClient updateAccountingClient(String id, Map<String, Object> fields) {
        for (int i = 0; i < accountingClients.size(); i++) {
            if (accountingClients.get(i).id().equals(id)) {
                AccountingClient updated = RecordPatcher.patch(accountingClients.get(i), fields);
                accountingClients.set(i, updated);
                return updated;
            }
        }
        throw new NoSuchElementException(id);
    }

    public void deleteAccountingClient(String id) {
        accountingClients.removeIf(r -> r.id().equals(id));
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
