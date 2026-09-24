package com.elo.datevmock.web;

import com.elo.datevmock.dms.DmsGenerator;
import com.elo.datevmock.json.DatevJsonMapper;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Ports {@code app/routers/dms.py}: {@code GET .../dms/v1/domains} and
 * {@code GET .../dms/v1/documents}. DMS has no official DATEV spec (see
 * {@code DmsGenerator}'s javadoc) — the schema and both endpoints are
 * JSON-only, bare arrays, no {@code Accept}-header negotiation, matching the
 * FastAPI source and its locked test contract in {@code tests/test_dms.py}
 * exactly rather than inferring anything more elaborate.
 */
@RestController
@RequestMapping("/datev/api/dms/v1")
public class DmsController {

    private final DmsGenerator generator;
    private final OverrideStore overrides;
    private final ObjectMapper jsonMapper = DatevJsonMapper.create();

    public DmsController(DmsGenerator generator, OverrideStore overrides) {
        this.generator = generator;
        this.overrides = overrides;
    }

    @GetMapping("/domains")
    public ResponseEntity<String> getDomains() {
        OverrideEntry override = overrides.getActiveOverride("dms.domains");
        if (override != null) {
            return overrideResponse(override);
        }
        return jsonResponse(writeJson(generator.domains()));
    }

    @GetMapping("/documents")
    public ResponseEntity<String> getDocuments() {
        OverrideEntry override = overrides.getActiveOverride("dms.documents");
        if (override != null) {
            return overrideResponse(override);
        }
        return jsonResponse(writeJson(generator.documents()));
    }

    private ResponseEntity<String> overrideResponse(OverrideEntry override) {
        MediaType mediaType = "xml".equals(override.contentType()) ? MediaType.APPLICATION_XML : MediaType.APPLICATION_JSON;
        return ResponseEntity.ok().contentType(mediaType).body(override.content());
    }

    private ResponseEntity<String> jsonResponse(String body) {
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_JSON).body(body);
    }

    private String writeJson(Object value) {
        try {
            return jsonMapper.writeValueAsString(value);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize DMS JSON response", e);
        }
    }
}
