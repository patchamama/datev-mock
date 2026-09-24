package com.elo.datevmock.web;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Ports {@code tests/test_diagnostics.py} against the SB8
 * {@link DiagnosticsController} — small endpoint, full case coverage rather
 * than representative sampling.
 */
@SpringBootTest
@AutoConfigureMockMvc
class DiagnosticsControllerTest {

    private static final String ECHO_ROOT_OPEN_TAG_PREFIX =
            "<Echo xmlns:i=\"http://www.w3.org/2001/XMLSchema-instance\" "
                    + "xmlns=\"http://schemas.datacontract.org/2004/07/Datev.ApplicationHost.Server.DataObjects\">";

    private static final Pattern ECHO_MESSAGE_RE =
            Pattern.compile("<echo_message>echo at (\\d{2}\\.\\d{2}\\.\\d{4} \\d{2}:\\d{2}:\\d{2})</echo_message>");
    private static final Pattern ID_RE = Pattern.compile("<id>([^<]+)</id>");

    @Autowired
    private MockMvc mockMvc;

    @Test
    void echoReturns200() throws Exception {
        mockMvc.perform(get("/datev/api/diagnostics/v1/echo")).andExpect(status().isOk());
    }

    @Test
    void echoContentTypeIsXml() throws Exception {
        mockMvc.perform(get("/datev/api/diagnostics/v1/echo"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_XML));
    }

    @Test
    void echoRootTagMatchesDatevContract() throws Exception {
        String body = performEcho();
        assertThat(body).startsWith("<?xml").contains(ECHO_ROOT_OPEN_TAG_PREFIX);
    }

    @Test
    void echoMessageMatchesExpectedFormat() throws Exception {
        String body = performEcho();
        Matcher matcher = ECHO_MESSAGE_RE.matcher(body);
        assertThat(matcher.find()).as("echo_message format in: " + body).isTrue();
    }

    @Test
    void echoIdIsAValidGuid() throws Exception {
        String body = performEcho();
        Matcher matcher = ID_RE.matcher(body);
        assertThat(matcher.find()).isTrue();
        UUID.fromString(matcher.group(1));
    }

    @Test
    void echoIdIsDynamicAcrossCalls() throws Exception {
        String first = performEcho();
        String second = performEcho();

        Matcher firstMatch = ID_RE.matcher(first);
        Matcher secondMatch = ID_RE.matcher(second);
        assertThat(firstMatch.find()).isTrue();
        assertThat(secondMatch.find()).isTrue();
        assertThat(firstMatch.group(1)).isNotEqualTo(secondMatch.group(1));
    }

    private String performEcho() throws Exception {
        MvcResult result = mockMvc.perform(get("/datev/api/diagnostics/v1/echo")).andReturn();
        return result.getResponse().getContentAsString();
    }
}
