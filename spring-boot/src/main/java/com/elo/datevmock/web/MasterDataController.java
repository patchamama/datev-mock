package com.elo.datevmock.web;

import com.elo.datevmock.json.DatevJsonMapper;
import com.elo.datevmock.masterdata.MasterDataClientJson;
import com.elo.datevmock.masterdata.MasterDataGenerator;
import com.elo.datevmock.model.Addressee;
import com.elo.datevmock.model.Bank;
import com.elo.datevmock.model.ClientResource;
import com.elo.datevmock.model.Employee;
import com.elo.datevmock.negotiation.FormatNegotiator;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.settings.MockSettings;
import com.elo.datevmock.store.RecordMapper;
import com.elo.datevmock.store.ReferenceValidation;
import com.elo.datevmock.store.StoredRecordStore;
import com.elo.datevmock.xml.ClientResourceXmlSerializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Ports {@code app/routers/master_data.py}: client, addressee, bank, and
 * employee reads/writes under {@code /datev/api/master-data/v1/*}. Composes
 * the SB2 (serialization/negotiation), SB3-sibling {@link MasterDataGenerator}
 * (fixed unscoped dataset, this master-data domain has no fiscal-year scope),
 * and SB4 (SQLite overlay) building blocks for the first time as real HTTP
 * endpoints.
 */
@RestController
@RequestMapping("/datev/api/master-data/v1")
public class MasterDataController {

    private static final String CLIENTS_RESOURCE = "master_data.clients";
    private static final String ADDRESSEES_RESOURCE = "master_data.addressees";
    private static final String BANKS_RESOURCE = "master_data.banks";
    private static final String EMPLOYEES_RESOURCE = "master_data.employees";
    private static final String RESPONSIBILITIES_RESOURCE = "master_data.client_responsibilities";

    // Ports `_CLIENT_RESOURCE_FIELD_MAP`: ClientWrite's snake_case body keys
    // -> ClientResource's Java (camelCase) record component names.
    private static final Map<String, String> CLIENT_FIELD_MAP = Map.ofEntries(
            Map.entry("id", "id"),
            Map.entry("client_since", "clientSince"),
            Map.entry("client_to", "clientTo"),
            Map.entry("differing_name", "differingName"),
            Map.entry("legal_person_id", "legalPersonId"),
            Map.entry("name", "name"),
            Map.entry("natural_person_id", "naturalPersonId"),
            Map.entry("note", "note"),
            Map.entry("number", "number"),
            Map.entry("status", "status"),
            Map.entry("timestamp", "timestamp"),
            Map.entry("type", "type"),
            Map.entry("organization_id", "organizationId"),
            Map.entry("organization_name", "organizationName"),
            Map.entry("organization_number", "organizationNumber"),
            Map.entry("establishment_id", "establishmentId"),
            Map.entry("establishment_name", "establishmentName"),
            Map.entry("establishment_number", "establishmentNumber"),
            Map.entry("establishment_short_name", "establishmentShortName"),
            Map.entry("functional_area_id", "functionalAreaId"),
            Map.entry("functional_area_name", "functionalAreaName"),
            Map.entry("functional_area_short_name", "functionalAreaShortName"));

    private final MasterDataGenerator generator;
    private final StoredRecordStore store;
    private final OverrideStore overrides;
    private final MockSettings settings;
    private final ObjectMapper jsonMapper = DatevJsonMapper.create();
    private final ObjectMapper plainJsonMapper = new ObjectMapper();

    public MasterDataController(
            MasterDataGenerator generator, StoredRecordStore store, OverrideStore overrides, MockSettings settings) {
        this.generator = generator;
        this.store = store;
        this.overrides = overrides;
        this.settings = settings;
    }

    // --- clients ---

    @GetMapping(value = "/clients")
    public ResponseEntity<String> getClients(@RequestHeader(value = "Accept", required = false) String accept) {
        OverrideEntry override = overrides.getActiveOverride("master_data.clients");
        if (override != null) {
            return overrideResponse(override);
        }

        List<ClientResource> merged = RecordMapper.mergeWithStored(
                generator.clientResources(), CLIENTS_RESOURCE, ClientResource.class,
                "id", CLIENT_FIELD_MAP, Set.of(), store, null, null);

        String format = FormatNegotiator.negotiate(accept, settings.getDefaultAccountingFormat());
        if (format.equals("json")) {
            return jsonResponse(writeJson(plainJsonMapper, MasterDataClientJson.project(merged)));
        }
        return xmlResponse(ClientResourceXmlSerializer.serialize(merged));
    }

    @PostMapping(value = "/clients", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postClient(@RequestBody Map<String, Object> body) {
        return writeRecord(CLIENTS_RESOURCE, body, null);
    }

    @PutMapping(value = "/clients/{clientId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putClient(@PathVariable String clientId, @RequestBody Map<String, Object> body) {
        return writeRecord(CLIENTS_RESOURCE, body, clientId);
    }

    @PutMapping(value = "/clients/{clientId}/responsibilities", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<Map<String, Object>> putClientResponsibilities(
            @PathVariable String clientId, @RequestBody List<Map<String, Object>> body) {
        Set<String> employeeIds = employeeIds();
        Set<String> clientResourceIds = clientResourceIds();
        for (Map<String, Object> item : body) {
            ReferenceValidation.validateReference(item.get("employee_id"), employeeIds, "employee_id");
            ReferenceValidation.validateReference(item.get("client_id"), clientResourceIds, "client_id");
        }

        store.deleteRecords(RESPONSIBILITIES_RESOURCE, clientId, null);
        return body.stream().map(item -> {
            String recordId = item.containsKey("id") ? String.valueOf(item.get("id")) : UUID.randomUUID().toString();
            return store.upsertRecord(RESPONSIBILITIES_RESOURCE, recordId, item, clientId, null);
        }).collect(Collectors.toList());
    }

    // --- addressees ---

    @GetMapping(value = "/addressees", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> getAddressees() {
        OverrideEntry override = overrides.getActiveOverride("master_data.addressees");
        if (override != null) {
            return overrideResponse(override);
        }
        List<Addressee> merged = RecordMapper.mergeWithStored(
                generator.addressees(), ADDRESSEES_RESOURCE, Addressee.class,
                "id", Map.of(), Set.of(), store, null, null);
        return jsonResponse(writeJson(jsonMapper, merged));
    }

    @GetMapping(value = "/addressees/{addresseeId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> getAddressee(@PathVariable String addresseeId) {
        return store.getRecord(ADDRESSEES_RESOURCE, addresseeId).orElseGet(() -> {
            Addressee fake = generator.addressees().stream()
                    .filter(a -> a.id().equals(addresseeId))
                    .findFirst()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "addressee not found"));
            return toMap(jsonMapper, fake);
        });
    }

    @PostMapping(value = "/addressees", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postAddressee(@RequestBody Map<String, Object> body) {
        return writeRecord(ADDRESSEES_RESOURCE, body, null);
    }

    @PutMapping(value = "/addressees/{addresseeId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putAddressee(@PathVariable String addresseeId, @RequestBody Map<String, Object> body) {
        return writeRecord(ADDRESSEES_RESOURCE, body, addresseeId);
    }

    // --- banks (read-only, no fake-vs-stored merge -- matches FastAPI, no POST/PUT route exists) ---

    @GetMapping(value = "/banks", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> getBanks() {
        OverrideEntry override = overrides.getActiveOverride("master_data.banks");
        if (override != null) {
            return overrideResponse(override);
        }
        return jsonResponse(writeJson(jsonMapper, generator.banks()));
    }

    // --- employees (no fake dataset -- store-only, same as FastAPI) ---

    @GetMapping(value = "/employees", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<Map<String, Object>> getEmployees() {
        return store.listRecords(EMPLOYEES_RESOURCE).stream()
                .map(row -> RecordMapper.fromStored(Employee.class, row, Map.of(), Set.of()))
                .map(record -> toMap(jsonMapper, record))
                .collect(Collectors.toList());
    }

    @GetMapping(value = "/employees/{employeeId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> getEmployee(@PathVariable String employeeId) {
        Map<String, Object> stored = store.getRecord(EMPLOYEES_RESOURCE, employeeId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "employee not found"));
        Employee employee = RecordMapper.fromStored(Employee.class, stored, Map.of(), Set.of());
        return toMap(jsonMapper, employee);
    }

    @PostMapping(value = "/employees", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> postEmployee(@RequestBody Map<String, Object> body) {
        return writeRecord(EMPLOYEES_RESOURCE, body, null);
    }

    @PutMapping(value = "/employees/{employeeId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> putEmployee(@PathVariable String employeeId, @RequestBody Map<String, Object> body) {
        return writeRecord(EMPLOYEES_RESOURCE, body, employeeId);
    }

    // --- shared helpers ---

    private Map<String, Object> writeRecord(String resourceType, Map<String, Object> body, String recordId) {
        String resolvedId = recordId != null ? recordId
                : (body.get("id") != null ? String.valueOf(body.get("id")) : UUID.randomUUID().toString());
        body.put("id", resolvedId);
        return store.upsertRecord(resourceType, resolvedId, body);
    }

    private Set<String> employeeIds() {
        return store.listRecords(EMPLOYEES_RESOURCE).stream()
                .map(row -> RecordMapper.fromStored(Employee.class, row, Map.of(), Set.of()).id())
                .collect(Collectors.toSet());
    }

    private Set<String> clientResourceIds() {
        List<ClientResource> merged = RecordMapper.mergeWithStored(
                generator.clientResources(), CLIENTS_RESOURCE, ClientResource.class,
                "id", CLIENT_FIELD_MAP, Set.of(), store, null, null);
        return merged.stream().map(ClientResource::id).collect(Collectors.toSet());
    }

    private ResponseEntity<String> overrideResponse(OverrideEntry override) {
        MediaType mediaType = "xml".equals(override.contentType()) ? MediaType.APPLICATION_XML : MediaType.APPLICATION_JSON;
        return ResponseEntity.ok().contentType(mediaType).body(override.content());
    }

    private ResponseEntity<String> xmlResponse(String body) {
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_XML).body(body);
    }

    private ResponseEntity<String> jsonResponse(String body) {
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(body);
    }

    private String writeJson(ObjectMapper mapper, Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize master-data JSON response", e);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(ObjectMapper mapper, Object value) {
        return mapper.convertValue(value, Map.class);
    }
}
