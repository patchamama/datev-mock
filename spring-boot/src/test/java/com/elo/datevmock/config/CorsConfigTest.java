package com.elo.datevmock.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Ports {@code app/main.py}'s CORS middleware config (commit {@code 3f71190}):
 * localhost/127.0.0.1 (any scheme, any port) is allowed, credentials are not,
 * every method/header is. Lets the admin frontend's configurable API base
 * URL (SB9) call this backend cross-origin.
 */
@SpringBootTest
@AutoConfigureMockMvc
class CorsConfigTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void allowsLocalhostOriginOnASimpleRequest() throws Exception {
        mockMvc.perform(get("/admin/api/settings").header(HttpHeaders.ORIGIN, "http://localhost:5173"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:5173"));
    }

    @Test
    void allows127001OriginOnASimpleRequest() throws Exception {
        mockMvc.perform(get("/admin/api/settings").header(HttpHeaders.ORIGIN, "https://127.0.0.1:58553"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "https://127.0.0.1:58553"));
    }

    @Test
    void preflightRequestIsAllowedWithAllMethodsAndHeaders() throws Exception {
        mockMvc.perform(options("/admin/api/settings")
                        .header(HttpHeaders.ORIGIN, "http://localhost:5173")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "PUT")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "content-type"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:5173"))
                .andExpect(header().exists(HttpHeaders.ACCESS_CONTROL_ALLOW_METHODS));
    }

    @Test
    void rejectsAnUnrelatedOrigin() throws Exception {
        mockMvc.perform(get("/admin/api/settings").header(HttpHeaders.ORIGIN, "https://evil.example.com"))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    /**
     * F6 (odd/tasks/datev-mock-standalone-frontend.md): a browser sending a
     * request from a {@code file://}-opened page (e.g. {@code
     * frontend/admin.html} double-clicked, or opened by {@code
     * start_java_datev_mock.bat/.sh}'s own post-launch browser-open) sets
     * {@code Origin: null} on its fetch() calls -- proves the literal
     * {@code "null"} pattern added to {@code ALLOWED_ORIGIN_PATTERNS} now
     * gets a matching {@code Access-Control-Allow-Origin} response header,
     * mirroring the equivalent {@code app/main.py} CORS change.
     */
    @Test
    void allowsTheLiteralNullOriginOnASimpleRequest() throws Exception {
        mockMvc.perform(get("/admin/api/settings").header(HttpHeaders.ORIGIN, "null"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "null"));
    }
}
