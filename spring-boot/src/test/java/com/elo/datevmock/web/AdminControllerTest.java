package com.elo.datevmock.web;

import com.elo.datevmock.admin.AdminDataStore;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.settings.MockSettings;
import com.elo.datevmock.store.StoredRecordStore;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Ports representative cases from {@code tests/test_admin_api.py} against the
 * SB9 {@link AdminController}: settings, master-data/accounting CRUD, reset,
 * stored records, request log (+ SSE smoke test), and override upload/
 * resolve/list/enable/delete. Not an exhaustive 1:1 port of every FastAPI
 * case -- one behavior-class per family (happy path, 404/400/422 where
 * applicable), matching the depth SB5-SB8 already established.
 */
@SpringBootTest
@AutoConfigureMockMvc
class AdminControllerTest {

    private static final Path SETTINGS_PATH = Path.of("settings.json");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AdminDataStore adminDataStore;

    @Autowired
    private StoredRecordStore storedRecordStore;

    @Autowired
    private OverrideStore overrideStore;

    @Autowired
    private MockSettings settings;

    private final ObjectMapper json = new ObjectMapper();

    // MockSettings is a Spring singleton shared with every other @SpringBootTest
    // class reusing this context (e.g. MasterDataControllerTest, which relies on
    // the default "xml" format) -- snapshotting and restoring it here, in
    // addition to resetting this test's own state, keeps putSettings*() tests
    // from leaking a mutated global format/version/port into unrelated test
    // classes that happen to run afterward in the same JVM.
    private int originalPort;
    private String originalFormat;
    private String originalApiVersion;

    @BeforeEach
    void resetSharedState() throws IOException {
        originalPort = settings.getPort();
        originalFormat = settings.getDefaultAccountingFormat();
        originalApiVersion = settings.getDatevApiVersion();
        adminDataStore.reset();
        storedRecordStore.reset();
        overrideStore.clearAllOverrides();
        Files.deleteIfExists(SETTINGS_PATH);
    }

    @AfterEach
    void restoreSharedState() throws IOException {
        settings.apply(originalPort, originalFormat, originalApiVersion);
        adminDataStore.reset();
        storedRecordStore.reset();
        overrideStore.clearAllOverrides();
        Files.deleteIfExists(SETTINGS_PATH);
    }

    // --- settings ---

    @Test
    void getSettingsReturnsSnakeCaseFields() throws Exception {
        mockMvc.perform(get("/admin/api/settings"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.port").exists())
                .andExpect(jsonPath("$.default_accounting_format").exists())
                .andExpect(jsonPath("$.datev_api_version").exists());
    }

    @Test
    void putSettingsAppliesAndReportsRestartRequiredOnPortChange() throws Exception {
        int currentPort = settings.getPort();
        String body = "{\"port\": " + (currentPort + 1)
                + ", \"default_accounting_format\": \"json\", \"datev_api_version\": \"modern\"}";

        mockMvc.perform(put("/admin/api/settings").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.port").value(currentPort + 1))
                .andExpect(jsonPath("$.default_accounting_format").value("json"))
                .andExpect(jsonPath("$.datev_api_version").value("modern"))
                .andExpect(jsonPath("$.restart_required").value(true));
    }

    @Test
    void putSettingsRejectsInvalidFormatWith400() throws Exception {
        int currentPort = settings.getPort();
        String body = "{\"port\": " + currentPort
                + ", \"default_accounting_format\": \"bogus\", \"datev_api_version\": \"legacy\"}";

        mockMvc.perform(put("/admin/api/settings").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").exists());
    }

    // --- master-data CRUD ---

    @Test
    void masterDataListReturnsPascalCaseKeys() throws Exception {
        MvcResult result = mockMvc.perform(get("/admin/api/clients/master-data"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThan(0);
        assertThat(records.get(0).has("Id")).isTrue();
        assertThat(records.get(0).has("Name")).isTrue();
    }

    @Test
    void postThenPutThenDeleteMasterDataRoundTrips() throws Exception {
        MvcResult postResult = mockMvc.perform(post("/admin/api/clients/master-data")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Admin Client\"}"))
                .andExpect(status().isCreated())
                .andReturn();
        String newId = json.readTree(postResult.getResponse().getContentAsString()).get("Id").asText();
        assertThat(newId).isNotBlank();

        mockMvc.perform(put("/admin/api/clients/master-data/" + newId)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Renamed Client\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.Name").value("Renamed Client"));

        mockMvc.perform(delete("/admin/api/clients/master-data/" + newId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"));
    }

    @Test
    void putUnknownMasterDataRecordReturns404() throws Exception {
        mockMvc.perform(put("/admin/api/clients/master-data/does-not-exist")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"X\"}"))
                .andExpect(status().isNotFound());
    }

    // --- accounting CRUD ---

    @Test
    void postThenPutThenDeleteAccountingClientRoundTrips() throws Exception {
        MvcResult postResult = mockMvc.perform(post("/admin/api/clients/accounting")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Acc Client\"}"))
                .andExpect(status().isCreated())
                .andReturn();
        String newId = json.readTree(postResult.getResponse().getContentAsString()).get("Id").asText();

        mockMvc.perform(put("/admin/api/clients/accounting/" + newId)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Renamed Acc\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.Name").value("Renamed Acc"));

        mockMvc.perform(delete("/admin/api/clients/accounting/" + newId))
                .andExpect(status().isOk());
    }

    @Test
    void putUnknownAccountingClientReturns404() throws Exception {
        mockMvc.perform(put("/admin/api/clients/accounting/does-not-exist")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"X\"}"))
                .andExpect(status().isNotFound());
    }

    // --- reset ---

    @Test
    void resetReturnsOkAndRestoresDatasetCardinality() throws Exception {
        mockMvc.perform(post("/admin/api/clients/master-data")
                .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Extra\"}"));

        mockMvc.perform(post("/admin/api/reset"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"));

        MvcResult result = mockMvc.perform(get("/admin/api/clients/master-data")).andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        // Reset regenerates the fixed-cardinality dataset -- "Extra" must be gone.
        for (JsonNode record : records) {
            assertThat(record.get("Name").asText()).isNotEqualTo("Extra");
        }
    }

    // --- stored records ---

    @Test
    void storedRecordsExposesEveryWrittenRecordWithSnakeCaseMeta() throws Exception {
        storedRecordStore.upsertRecord("master_data.employees", "emp-1", java.util.Map.of("name", "Jane"));

        mockMvc.perform(get("/admin/api/stored-records"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.record_id == 'emp-1')]").exists())
                .andExpect(jsonPath("$[?(@.record_id == 'emp-1')].resource_type").value("master_data.employees"));
    }

    // --- request log ---

    @Test
    void logsEndpointReturnsBacklogAsJsonArray() throws Exception {
        mockMvc.perform(get("/admin/api/clients/master-data")); // generate at least one log entry

        mockMvc.perform(get("/admin/api/logs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test
    void logsStreamRespondsWithEventStreamContentType() throws Exception {
        mockMvc.perform(get("/admin/api/logs/stream"))
                .andExpect(request().asyncStarted())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM));
    }

    // --- overrides ---

    @Test
    void uploadingUnrecognizedContentReturns422() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "garbage.txt", "text/plain", "not xml, not json".getBytes());

        mockMvc.perform(MockMvcRequestBuilders.multipart("/admin/api/overrides").file(file))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.status").value("unrecognized"));
    }

    @Test
    void uploadingUnambiguousJsonMatchesAndListsAsOverride() throws Exception {
        String content = "{\"bic\": \"XYZ\", \"country_code\": \"DE\"}";
        MockMultipartFile file = new MockMultipartFile(
                "file", "bank.json", "application/json", content.getBytes());

        mockMvc.perform(MockMvcRequestBuilders.multipart("/admin/api/overrides").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("matched"))
                .andExpect(jsonPath("$.endpoint").value("master_data.banks"));

        mockMvc.perform(get("/admin/api/overrides"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$['master_data.banks'].enabled").value(true))
                .andExpect(jsonPath("$['master_data.banks'].content").doesNotExist());

        mockMvc.perform(put("/admin/api/overrides/master_data.banks")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"enabled\": false}"))
                .andExpect(status().isOk());
        mockMvc.perform(get("/admin/api/overrides"))
                .andExpect(jsonPath("$['master_data.banks'].enabled").value(false));

        mockMvc.perform(delete("/admin/api/overrides/master_data.banks")).andExpect(status().isOk());
        mockMvc.perform(get("/admin/api/overrides")).andExpect(jsonPath("$['master_data.banks']").doesNotExist());
    }

    @Test
    void uploadingAmbiguousContentReturnsPendingIdThenResolvesToChosenCandidate() throws Exception {
        // Matches the documented ambiguous creditors/debitors fingerprint group.
        String content = "{\"addressee_id\": \"a\", \"business_partner_number\": \"1\", \"legal_entity_type\": \"x\"}";
        MockMultipartFile file = new MockMultipartFile(
                "file", "partner.json", "application/json", content.getBytes());

        MvcResult uploadResult = mockMvc.perform(MockMvcRequestBuilders.multipart("/admin/api/overrides").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ambiguous"))
                .andReturn();
        JsonNode uploadBody = json.readTree(uploadResult.getResponse().getContentAsString());
        String pendingId = uploadBody.get("pending_id").asText();

        String resolveBody = "{\"pending_id\": \"" + pendingId + "\", \"endpoint\": \"accounting.debitors\"}";
        mockMvc.perform(post("/admin/api/overrides/resolve")
                        .contentType(MediaType.APPLICATION_JSON).content(resolveBody))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"));

        mockMvc.perform(get("/admin/api/overrides"))
                .andExpect(jsonPath("$['accounting.debitors']").exists());
    }

    @Test
    void resolvingUnknownPendingIdReturns400() throws Exception {
        String resolveBody = "{\"pending_id\": \"no-such-id\", \"endpoint\": \"accounting.debitors\"}";
        mockMvc.perform(post("/admin/api/overrides/resolve")
                        .contentType(MediaType.APPLICATION_JSON).content(resolveBody))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").exists());
    }
}
