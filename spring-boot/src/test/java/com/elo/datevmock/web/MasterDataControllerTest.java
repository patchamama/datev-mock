package com.elo.datevmock.web;

import com.elo.datevmock.store.StoredRecordStore;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Ports representative cases from {@code tests/test_master_data.py} and
 * {@code tests/test_master_data_addressees_banks.py} against the SB5 Spring
 * controllers. Not an exhaustive 1:1 port of all ~40 FastAPI test cases —
 * covers list/detail/create/update, 404, content negotiation, and the
 * responsibilities FK-validation 422 path.
 */
@SpringBootTest
@AutoConfigureMockMvc
class MasterDataControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private StoredRecordStore store;

    private final ObjectMapper json = new ObjectMapper();

    @BeforeEach
    void resetStore() {
        store.reset();
    }

    // --- clients ---

    @Test
    void clientsDefaultFormatIsXml() throws Exception {
        mockMvc.perform(get("/datev/api/master-data/v1/clients"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_XML))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("<ArrayOfClientResource")));
    }

    @Test
    void clientsHasAtLeast15Records() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/clients"))
                .andExpect(status().isOk())
                .andReturn();
        String body = result.getResponse().getContentAsString();
        int count = body.split("<ClientResource>", -1).length - 1;
        assertThat(count).isGreaterThanOrEqualTo(15);
    }

    @Test
    void clientsJsonProjectionHasCoreFields() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThanOrEqualTo(15);
        JsonNode first = records.get(0);
        assertThat(first.has("id")).isTrue();
        assertThat(first.has("name")).isTrue();
        assertThat(first.get("number").isInt()).isTrue();
    }

    @Test
    void postThenGetClientRoundTripsThroughStore() throws Exception {
        String body = """
                {"name": "New Client", "number": 9999, "type": "legal_person", "status": "active", "timestamp": "2024-01-01T00:00:00+01:00"}
                """;
        MvcResult postResult = mockMvc.perform(post("/datev/api/master-data/v1/clients")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated())
                .andReturn();
        JsonNode created = json.readTree(postResult.getResponse().getContentAsString());
        String newId = created.get("id").asText();
        assertThat(newId).isNotBlank();

        MvcResult listResult = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode records = json.readTree(listResult.getResponse().getContentAsString());
        boolean found = false;
        for (JsonNode record : records) {
            if (record.get("id").asText().equals(newId)) {
                found = true;
                assertThat(record.get("name").asText()).isEqualTo("New Client");
            }
        }
        assertThat(found).isTrue();
    }

    // --- addressees ---

    @Test
    void addresseesReturnsBareJsonArrayWithMinimumRecords() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/addressees"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.isArray()).isTrue();
        assertThat(records.size()).isGreaterThanOrEqualTo(6);
    }

    @Test
    void addresseeDetailUnknownIdReturns404() throws Exception {
        mockMvc.perform(get("/datev/api/master-data/v1/addressees/does-not-exist"))
                .andExpect(status().isNotFound());
    }

    @Test
    void addresseeDetailValidIdReturns200() throws Exception {
        MvcResult listResult = mockMvc.perform(get("/datev/api/master-data/v1/addressees")).andReturn();
        JsonNode records = json.readTree(listResult.getResponse().getContentAsString());
        String firstId = records.get(0).get("id").asText();

        mockMvc.perform(get("/datev/api/master-data/v1/addressees/" + firstId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(firstId));
    }

    // --- banks ---

    @Test
    void banksReturnsBareJsonArrayWithMinimumRecords() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/master-data/v1/banks"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andReturn();
        JsonNode records = json.readTree(result.getResponse().getContentAsString());
        assertThat(records.size()).isGreaterThanOrEqualTo(4);
        JsonNode first = records.get(0);
        assertThat(first.has("bank_code")).isTrue();
        assertThat(first.has("bic")).isTrue();
    }

    // --- employees ---

    @Test
    void employeeDetailUnknownIdReturns404() throws Exception {
        mockMvc.perform(get("/datev/api/master-data/v1/employees/does-not-exist"))
                .andExpect(status().isNotFound());
    }

    @Test
    void postThenGetEmployeeRoundTrips() throws Exception {
        String body = """
                {"name": "Jane Doe", "natural_person_id": "np-1"}
                """;
        MvcResult postResult = mockMvc.perform(post("/datev/api/master-data/v1/employees")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated())
                .andReturn();
        JsonNode created = json.readTree(postResult.getResponse().getContentAsString());
        String newId = created.get("id").asText();

        mockMvc.perform(get("/datev/api/master-data/v1/employees/" + newId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Jane Doe"));
    }

    // --- responsibilities FK validation ---

    @Test
    void responsibilitiesRejectsUnknownEmployeeIdWith422() throws Exception {
        MvcResult listResult = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andReturn();
        JsonNode clients = json.readTree(listResult.getResponse().getContentAsString());
        String clientId = clients.get(0).get("id").asText();

        String body = "[{\"employee_id\": \"does-not-exist\"}]";
        mockMvc.perform(put("/datev/api/master-data/v1/clients/" + clientId + "/responsibilities")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isUnprocessableEntity());
    }

    @Test
    void responsibilitiesAcceptsValidReferencesAndReplacesPriorSet() throws Exception {
        MvcResult clientsResult = mockMvc.perform(get("/datev/api/master-data/v1/clients").header("Accept", "application/json"))
                .andReturn();
        String clientId = json.readTree(clientsResult.getResponse().getContentAsString()).get(0).get("id").asText();

        MvcResult employeeResult = mockMvc.perform(post("/datev/api/master-data/v1/employees")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \"Resp Employee\", \"natural_person_id\": \"np-2\"}"))
                .andReturn();
        String employeeId = json.readTree(employeeResult.getResponse().getContentAsString()).get("id").asText();

        String body = "[{\"employee_id\": \"" + employeeId + "\", \"client_id\": \"" + clientId + "\"}]";
        mockMvc.perform(put("/datev/api/master-data/v1/clients/" + clientId + "/responsibilities")
                        .contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].employee_id").value(employeeId));
    }
}
