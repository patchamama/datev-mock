package com.elo.datevmock.web;

import com.elo.datevmock.admin.AdminDataStore;
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
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

/**
 * SB12: proves {@link AdminDataStore}'s master-data/accounting-client CRUD
 * now shares live state with SB5's {@code MasterDataController} and SB6's
 * {@code AccountingController} public GET routes, instead of each side
 * keeping its own independent generator/state (the gap SB9 introduced and
 * SB10 documented). Before the SB12 retrofit, every "visible on the other
 * side" assertion below failed (RED) because {@code AdminDataStore} wrote to
 * its own {@code CopyOnWriteArrayList}, never to the {@link StoredRecordStore}
 * rows the public controllers actually merge over their generators.
 */
@SpringBootTest
@AutoConfigureMockMvc
class AdminStateSharingTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AdminDataStore adminDataStore;

    @Autowired
    private StoredRecordStore storedRecordStore;

    private final ObjectMapper json = new ObjectMapper();

    @BeforeEach
    void resetSharedState() {
        adminDataStore.reset();
        storedRecordStore.reset();
    }

    @AfterEach
    void restoreSharedState() {
        adminDataStore.reset();
        storedRecordStore.reset();
    }

    // --- master-data clients: admin write -> public read ---

    @Test
    void adminCreatedMasterDataClientIsVisibleOnPublicClientsRead() throws Exception {
        MvcResult postResult = mockMvc.perform(post("/admin/api/clients/master-data")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Admin Shared Client\"}"))
                .andReturn();
        String newId = json.readTree(postResult.getResponse().getContentAsString()).get("Id").asText();

        JsonNode publicRecord = findMasterDataClient(newId);
        assertThat(publicRecord).as("admin-created master-data client visible on public GET").isNotNull();
        assertThat(publicRecord.get("name").asText()).isEqualTo("Admin Shared Client");
    }

    @Test
    void adminUpdatedMasterDataClientIsVisibleOnPublicClientsRead() throws Exception {
        String existingId = firstPublicMasterDataClientId();

        mockMvc.perform(put("/admin/api/clients/master-data/" + existingId)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Renamed By Admin\"}"))
                .andReturn();

        JsonNode publicRecord = findMasterDataClient(existingId);
        assertThat(publicRecord).as("admin-updated master-data client visible on public GET").isNotNull();
        assertThat(publicRecord.get("name").asText()).isEqualTo("Renamed By Admin");
    }

    @Test
    void adminDeletedMasterDataClientDisappearsFromPublicClientsRead() throws Exception {
        String existingId = firstPublicMasterDataClientId();

        mockMvc.perform(delete("/admin/api/clients/master-data/" + existingId)).andReturn();

        JsonNode publicRecord = findMasterDataClient(existingId);
        assertThat(publicRecord).as("admin-deleted master-data client absent from public GET").isNull();
    }

    // --- master-data clients: public write -> admin read (reverse direction; already-separate before SB12) ---

    @Test
    void publicWrittenMasterDataClientIsVisibleOnAdminRead() throws Exception {
        MvcResult postResult = mockMvc.perform(post("/datev/api/master-data/v1/clients")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"name\": \"Public Written Client\"}"))
                .andReturn();
        String newId = json.readTree(postResult.getResponse().getContentAsString()).get("id").asText();

        MvcResult adminListResult = mockMvc.perform(get("/admin/api/clients/master-data")).andReturn();
        JsonNode adminRecords = json.readTree(adminListResult.getResponse().getContentAsString());
        JsonNode found = null;
        for (JsonNode record : adminRecords) {
            if (record.get("Id").asText().equals(newId)) {
                found = record;
            }
        }
        assertThat(found).as("publicly-written master-data client visible on admin GET").isNotNull();
        assertThat(found.get("Name").asText()).isEqualTo("Public Written Client");
    }

    // --- accounting clients: admin write -> public read ---

    @Test
    void adminCreatedAccountingClientIsVisibleOnPublicAccountingClientsRead() throws Exception {
        MvcResult postResult = mockMvc.perform(post("/admin/api/clients/accounting")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Admin Shared Accounting\"}"))
                .andReturn();
        String newId = json.readTree(postResult.getResponse().getContentAsString()).get("Id").asText();

        JsonNode publicRecord = findAccountingClient(newId);
        assertThat(publicRecord).as("admin-created accounting client visible on public GET").isNotNull();
        assertThat(publicRecord.get("name").asText()).isEqualTo("Admin Shared Accounting");
    }

    @Test
    void adminUpdatedAccountingClientIsVisibleOnPublicAccountingClientsRead() throws Exception {
        String existingId = firstPublicAccountingClientId();

        mockMvc.perform(put("/admin/api/clients/accounting/" + existingId)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"Name\": \"Renamed Accounting\"}"))
                .andReturn();

        JsonNode publicRecord = findAccountingClient(existingId);
        assertThat(publicRecord).as("admin-updated accounting client visible on public GET").isNotNull();
        assertThat(publicRecord.get("name").asText()).isEqualTo("Renamed Accounting");
    }

    @Test
    void adminDeletedAccountingClientDisappearsFromPublicAccountingClientsRead() throws Exception {
        String existingId = firstPublicAccountingClientId();

        mockMvc.perform(delete("/admin/api/clients/accounting/" + existingId)).andReturn();

        JsonNode publicRecord = findAccountingClient(existingId);
        assertThat(publicRecord).as("admin-deleted accounting client absent from public GET").isNull();
    }

    // --- helpers ---

    private String firstPublicMasterDataClientId() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andReturn();
        return json.readTree(result.getResponse().getContentAsString()).get(0).get("id").asText();
    }

    private JsonNode findMasterDataClient(String id) throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        for (JsonNode record : records) {
            if (record.get("id").asText().equals(id)) {
                return record;
            }
        }
        return null;
    }

    private String firstPublicAccountingClientId() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/accounting/v1/clients").header("Accept", "application/json"))
                .andReturn();
        return json.readTree(result.getResponse().getContentAsString()).get(0).get("id").asText();
    }

    private JsonNode findAccountingClient(String id) throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/accounting/v1/clients").header("Accept", "application/json"))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        for (JsonNode record : records) {
            if (record.get("id").asText().equals(id)) {
                return record;
            }
        }
        return null;
    }
}
