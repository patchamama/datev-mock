package com.elo.datevmock.web;

import com.elo.datevmock.model.Echo;
import com.elo.datevmock.overrides.OverrideEntry;
import com.elo.datevmock.overrides.OverrideStore;
import com.elo.datevmock.xml.EchoXmlSerializer;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.UUID;

/**
 * Ports {@code app/routers/diagnostics.py}: {@code GET
 * .../diagnostics/v1/echo}. Always XML (no negotiation — FastAPI's own
 * handler hardcodes {@code media_type="application/xml"}, no {@code Accept}
 * check on the non-override path), freshly generated per call: a new GUID
 * {@code id} and an {@code echo_message} carrying the current timestamp in
 * {@code "echo at DD.MM.YYYY HH:MM:SS"} format every single request.
 */
@RestController
@RequestMapping("/datev/api/diagnostics/v1")
public class DiagnosticsController {

    private static final DateTimeFormatter ECHO_MESSAGE_FORMAT = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm:ss");

    private final OverrideStore overrides;

    public DiagnosticsController(OverrideStore overrides) {
        this.overrides = overrides;
    }

    @GetMapping("/echo")
    public ResponseEntity<String> getEcho() {
        OverrideEntry override = overrides.getActiveOverride("diagnostics.echo");
        if (override != null) {
            MediaType mediaType = "xml".equals(override.contentType()) ? MediaType.APPLICATION_XML : MediaType.APPLICATION_JSON;
            return ResponseEntity.ok().contentType(mediaType).body(override.content());
        }

        Echo echo = new Echo("echo at " + LocalDateTime.now().format(ECHO_MESSAGE_FORMAT), UUID.randomUUID().toString());
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_XML).body(EchoXmlSerializer.serialize(echo));
    }
}
