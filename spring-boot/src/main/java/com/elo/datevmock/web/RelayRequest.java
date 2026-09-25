package com.elo.datevmock.web;

import java.util.Map;

/**
 * Ports the Python relay's {@code RelayRequest} Pydantic model
 * ({@code app/routers/relay.py}): {@code {method, url, headers?, body?,
 * auth?}}. Deserialized directly from the JSON request body by Spring's
 * default Jackson {@code ObjectMapper} -- every field name here already
 * matches the wire JSON key verbatim (no snake_case/PascalCase translation
 * needed, unlike the admin master-data/accounting record shapes elsewhere
 * in this package).
 */
public record RelayRequest(String method, String url, Map<String, String> headers, String body, RelayAuth auth) {
}
