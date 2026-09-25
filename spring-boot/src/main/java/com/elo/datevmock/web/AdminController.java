package com.elo.datevmock.web;

import com.elo.datevmock.admin.AdminDataStore;
import com.elo.datevmock.admin.RequestLogEntry;
import com.elo.datevmock.admin.RequestLogStore;
import com.elo.datevmock.overrides.OverrideDetector;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.settings.MockSettings;
import com.elo.datevmock.store.StoredRecordStore;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.json.JsonMapper;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * Ports {@code app/routers/admin.py}'s JSON API section (everything above
 * the presentational-only "API catalog"): settings, master-data/accounting
 * CRUD, reset, stored records, live request-log + SSE, and custom-override
 * upload/resolve/list/enable/delete -- everything under {@code /admin/api/*}.
 * The existing {@code /admin} frontend page itself continues to be served
 * only by FastAPI (see the "same frontend, configurable backend URL"
 * decision in the epic doc); this backend only needs matching JSON/SSE
 * endpoints plus CORS ({@link com.elo.datevmock.config.CorsConfig}) for that
 * page to call it cross-origin.
 */
@RestController
@RequestMapping("/admin/api")
public class AdminController {

    private static final String MASTER_DATA_NOT_FOUND = "master-data record not found";
    private static final String ACCOUNTING_CLIENT_NOT_FOUND = "accounting client not found";
    private static final long SSE_KEEPALIVE_SECONDS = 15L;

    // Ports app/data_store.py's ClientResource/Client dataclasses, which use
    // PascalCase field names (Id, Name, EstablishmentId, ...) directly as
    // their attribute names -- asdict() therefore renders admin master-data/
    // accounting-client JSON with those exact PascalCase keys, distinct from
    // the snake_case DatevJsonMapper convention used by the public read
    // endpoints (SB5/SB6). The admin frontend's edit grid reads/writes these
    // same PascalCase keys (see AdminDataStore/RecordPatcher, which already
    // check the PascalCase spelling first for incoming write bodies).
    private static final ObjectMapper ADMIN_RECORD_MAPPER =
            JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.UPPER_CAMEL_CASE).build();

    // Ports app/db.py::list_all_with_meta and app/request_log.py::LogEntry,
    // both plain snake_case dataclass/dict shapes.
    private static final ObjectMapper SNAKE_CASE_MAPPER =
            JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();

    private final MockSettings settings;
    private final AdminDataStore adminDataStore;
    private final StoredRecordStore storedRecordStore;
    private final RequestLogStore requestLogStore;
    private final OverrideStore overrideStore;
    private final OverrideDetector overrideDetector;

    public AdminController(
            MockSettings settings,
            AdminDataStore adminDataStore,
            StoredRecordStore storedRecordStore,
            RequestLogStore requestLogStore,
            OverrideStore overrideStore,
            OverrideDetector overrideDetector) {
        this.settings = settings;
        this.adminDataStore = adminDataStore;
        this.storedRecordStore = storedRecordStore;
        this.requestLogStore = requestLogStore;
        this.overrideStore = overrideStore;
        this.overrideDetector = overrideDetector;
    }

    // --- settings ---

    @GetMapping("/settings")
    public Map<String, Object> getSettings() {
        return settingsMap(null);
    }

    @PutMapping("/settings")
    public ResponseEntity<Map<String, Object>> putSettings(@RequestBody Map<String, Object> body) {
        try {
            int port = ((Number) body.get("port")).intValue();
            String format = String.valueOf(body.get("default_accounting_format"));
            Object apiVersionRaw = body.get("datev_api_version");
            String apiVersion = apiVersionRaw != null ? String.valueOf(apiVersionRaw) : "legacy";

            boolean restartRequired = settings.apply(port, format, apiVersion);
            return ResponseEntity.ok(settingsMap(restartRequired));
        } catch (IllegalArgumentException | ClassCastException | NullPointerException e) {
            return ResponseEntity.badRequest().body(Map.of("detail", String.valueOf(e.getMessage())));
        }
    }

    private Map<String, Object> settingsMap(Boolean restartRequired) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("port", settings.getPort());
        result.put("default_accounting_format", settings.getDefaultAccountingFormat());
        result.put("datev_api_version", settings.getDatevApiVersion());
        if (restartRequired != null) {
            result.put("restart_required", restartRequired);
        }
        return result;
    }

    // --- master-data CRUD ---

    @GetMapping(value = "/clients/master-data", produces = MediaType.APPLICATION_JSON_VALUE)
    public String getMasterData() {
        return writeJson(adminDataStore.listMasterData());
    }

    @PostMapping(value = "/clients/master-data", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public String postMasterData(@RequestBody Map<String, Object> fields) {
        return writeJson(adminDataStore.addMasterData(fields));
    }

    @PutMapping(value = "/clients/master-data/{recordId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public String putMasterData(@PathVariable String recordId, @RequestBody Map<String, Object> fields) {
        try {
            return writeJson(adminDataStore.updateMasterData(recordId, fields));
        } catch (NoSuchElementException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, MASTER_DATA_NOT_FOUND);
        }
    }

    @DeleteMapping("/clients/master-data/{recordId}")
    public Map<String, Object> deleteMasterData(@PathVariable String recordId) {
        adminDataStore.deleteMasterData(recordId);
        return Map.of("status", "ok");
    }

    // --- accounting CRUD ---

    @GetMapping(value = "/clients/accounting", produces = MediaType.APPLICATION_JSON_VALUE)
    public String getAccountingClientsAdmin() {
        return writeJson(adminDataStore.listAccountingClients());
    }

    @PostMapping(value = "/clients/accounting", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public String postAccountingClient(@RequestBody Map<String, Object> fields) {
        return writeJson(adminDataStore.addAccountingClient(fields));
    }

    @PutMapping(value = "/clients/accounting/{recordId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public String putAccountingClient(@PathVariable String recordId, @RequestBody Map<String, Object> fields) {
        try {
            return writeJson(adminDataStore.updateAccountingClient(recordId, fields));
        } catch (NoSuchElementException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, ACCOUNTING_CLIENT_NOT_FOUND);
        }
    }

    @DeleteMapping("/clients/accounting/{recordId}")
    public Map<String, Object> deleteAccountingClient(@PathVariable String recordId) {
        adminDataStore.deleteAccountingClient(recordId);
        return Map.of("status", "ok");
    }

    // --- reset ---

    @PostMapping("/reset")
    public Map<String, Object> resetData() {
        adminDataStore.reset();
        return Map.of("status", "ok");
    }

    // --- stored records ---

    @GetMapping(value = "/stored-records", produces = MediaType.APPLICATION_JSON_VALUE)
    public String getStoredRecords() {
        return writeSnakeCaseJson(storedRecordStore.listAllWithMeta());
    }

    // --- request log ---

    @GetMapping(value = "/logs", produces = MediaType.APPLICATION_JSON_VALUE)
    public String getLogs() {
        return writeSnakeCaseJson(requestLogStore.getBacklog());
    }

    @GetMapping(value = "/logs/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter getLogsStream() {
        SseEmitter emitter = new SseEmitter(0L);
        Thread worker = new Thread(() -> runLogStream(emitter), "admin-logs-sse");
        worker.setDaemon(true);
        worker.start();
        return emitter;
    }

    private void runLogStream(SseEmitter emitter) {
        BlockingQueue<RequestLogEntry> queue = null;
        try {
            for (RequestLogEntry entry : requestLogStore.getBacklog()) {
                emitter.send(SseEmitter.event().data(writeSnakeCaseJson(entry)));
            }
            queue = requestLogStore.registerSubscriber();
            while (true) {
                RequestLogEntry entry = queue.poll(SSE_KEEPALIVE_SECONDS, TimeUnit.SECONDS);
                if (entry == null) {
                    emitter.send(SseEmitter.event().comment("keep-alive"));
                } else {
                    emitter.send(SseEmitter.event().data(writeSnakeCaseJson(entry)));
                }
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            emitter.completeWithError(e);
        } finally {
            if (queue != null) {
                requestLogStore.unregisterSubscriber(queue);
            }
        }
    }

    // --- overrides ---

    @PostMapping(value = "/overrides", consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> postOverride(@RequestParam("file") MultipartFile file)
            throws IOException {
        String content;
        try {
            content = decodeUtf8Strict(file.getBytes());
        } catch (CharacterCodingException e) {
            return ResponseEntity.unprocessableEntity().body(Map.of("status", "unrecognized"));
        }

        content = overrideDetector.sanitizeXml(content);

        List<String> candidates = overrideDetector.detectCandidates(content);
        if (candidates.isEmpty()) {
            return ResponseEntity.unprocessableEntity().body(Map.of("status", "unrecognized"));
        }

        String contentType = overrideDetector.detectContentType(content);
        if (contentType == null) {
            contentType = "json";
        }
        String filename = file.getOriginalFilename();
        if (filename == null || filename.isBlank()) {
            filename = "upload";
        }

        if (candidates.size() == 1) {
            overrideStore.setOverride(candidates.get(0), content, contentType, filename);
            return ResponseEntity.ok(Map.of("status", "matched", "endpoint", candidates.get(0)));
        }

        String pendingId = overrideStore.storePending(content, contentType, filename, candidates);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", "ambiguous");
        body.put("candidates", candidates);
        body.put("pending_id", pendingId);
        return ResponseEntity.ok(body);
    }

    @PostMapping(value = "/overrides/resolve", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> resolveOverride(@RequestBody Map<String, Object> body) {
        String pendingId = String.valueOf(body.get("pending_id"));
        String endpoint = String.valueOf(body.get("endpoint"));
        try {
            overrideStore.resolvePending(pendingId, endpoint);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("detail", e.getMessage()));
        }
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    @GetMapping(value = "/overrides", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> getOverrides() {
        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<String, OverrideEntry> entry : overrideStore.listOverrides().entrySet()) {
            OverrideEntry value = entry.getValue();
            Map<String, Object> projected = new LinkedHashMap<>();
            projected.put("content_type", value.contentType());
            projected.put("filename", value.filename());
            projected.put("uploaded_at", value.uploadedAt());
            projected.put("enabled", value.enabled());
            result.put(entry.getKey(), projected);
        }
        return result;
    }

    @PutMapping("/overrides/{key}")
    public Map<String, Object> setOverrideEnabled(@PathVariable String key, @RequestBody Map<String, Object> body) {
        boolean enabled = Boolean.TRUE.equals(body.get("enabled"));
        overrideStore.setEnabled(key, enabled);
        return Map.of("status", "ok");
    }

    @DeleteMapping("/overrides/{key}")
    public Map<String, Object> deleteOverride(@PathVariable String key) {
        overrideStore.deleteOverride(key);
        return Map.of("status", "ok");
    }

    // --- shared helpers ---

    private static String decodeUtf8Strict(byte[] raw) throws CharacterCodingException {
        CharsetDecoder decoder = StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT);
        return decoder.decode(ByteBuffer.wrap(raw)).toString();
    }

    private static String writeJson(Object value) {
        try {
            return ADMIN_RECORD_MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize admin JSON response", e);
        }
    }

    private static String writeSnakeCaseJson(Object value) {
        try {
            return SNAKE_CASE_MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize admin JSON response", e);
        }
    }
}
