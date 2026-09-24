package com.elo.datevmock.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Ports representative cases from {@code tests/test_dms.py} against the SB8
 * {@link DmsController} — shape/type assertions only, matching the Python
 * source's own "self-designed schema" caveat (no exact invented values are
 * ever asserted, there).
 */
@SpringBootTest
@AutoConfigureMockMvc
class DmsControllerTest {

    private static final Set<String> DOMAIN_TYPES = Set.of("domain", "folder", "register");
    private static final Set<String> DOCUMENT_CLASSES = Set.of("invoice", "receipt", "contract", "delivery_note");

    @Autowired
    private MockMvc mockMvc;

    private final ObjectMapper json = new ObjectMapper();

    private JsonNode getDomains() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/dms/v1/domains")).andReturn();
        return json.readTree(result.getResponse().getContentAsString());
    }

    private JsonNode getDocuments() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/dms/v1/documents")).andReturn();
        return json.readTree(result.getResponse().getContentAsString());
    }

    @Test
    void domainsReturns200Json() throws Exception {
        mockMvc.perform(get("/datev/api/dms/v1/domains"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON));
    }

    @Test
    void domainsBodyIsBareArrayWithMinimumRecords() throws Exception {
        JsonNode records = getDomains();
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThanOrEqualTo(5);
    }

    @Test
    void domainRecordHasCoreFieldsAndMultipleLevels() throws Exception {
        JsonNode records = getDomains();
        Set<String> typesSeen = new HashSet<>();
        for (JsonNode record : records) {
            assertThat(record.get("id").asText()).isNotBlank();
            assertThat(record.get("name").asText()).isNotBlank();
            String type = record.get("type").asText();
            assertThat(DOMAIN_TYPES).contains(type);
            typesSeen.add(type);
        }
        assertThat(typesSeen.size()).isGreaterThanOrEqualTo(2);
    }

    @Test
    void rootDomainRecordsHaveNoParentIdField() throws Exception {
        JsonNode records = getDomains();
        boolean sawRoot = false;
        for (JsonNode record : records) {
            if ("domain".equals(record.get("type").asText())) {
                sawRoot = true;
                assertThat(record.has("parent_id")).isFalse();
            }
        }
        assertThat(sawRoot).isTrue();
    }

    @Test
    void nonRootDomainRecordsHaveParentIdReferencingKnownId() throws Exception {
        JsonNode records = getDomains();
        Set<String> knownIds = new HashSet<>();
        records.forEach(r -> knownIds.add(r.get("id").asText()));

        boolean sawNonRoot = false;
        for (JsonNode record : records) {
            String type = record.get("type").asText();
            if (type.equals("folder") || type.equals("register")) {
                sawNonRoot = true;
                assertThat(record.has("parent_id")).isTrue();
                assertThat(knownIds).contains(record.get("parent_id").asText());
            }
        }
        assertThat(sawNonRoot).isTrue();
    }

    @Test
    void documentsReturns200Json() throws Exception {
        mockMvc.perform(get("/datev/api/dms/v1/documents"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON));
    }

    @Test
    void documentsBodyIsBareArrayWithMinimumRecords() throws Exception {
        JsonNode records = getDocuments();
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThanOrEqualTo(5);
    }

    @Test
    void documentRecordHasCoreFieldsAndValidGuidAndMultipleClasses() throws Exception {
        JsonNode documents = getDocuments();
        JsonNode domains = getDomains();
        Set<String> knownDomainIds = new HashSet<>();
        domains.forEach(d -> knownDomainIds.add(d.get("id").asText()));

        Set<String> classesSeen = new HashSet<>();
        for (JsonNode record : documents) {
            assertThat(record.get("id").asText()).isNotBlank();
            UUID.fromString(record.get("id").asText());
            assertThat(record.get("name").asText()).isNotBlank();
            assertThat(record.get("amount").asDouble()).isGreaterThan(0);
            String documentClass = record.get("document_class").asText();
            assertThat(DOCUMENT_CLASSES).contains(documentClass);
            classesSeen.add(documentClass);
            assertThat(record.get("created_at").asText()).isNotBlank();
            assertThat(record.get("modified_at").asText()).isNotBlank();
            assertThat(knownDomainIds).contains(record.get("domain_id").asText());
        }
        assertThat(classesSeen.size()).isGreaterThanOrEqualTo(2);
    }
}
