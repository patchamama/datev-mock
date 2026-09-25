package com.elo.datevmock.admin;

import java.util.Map;

/** Ports {@code app/request_log.py::LogEntry}. */
public record RequestLogEntry(
        long seq,
        String timestamp,
        String method,
        String path,
        String queryString,
        String routePath,
        Map<String, String> pathParams,
        Map<String, String> queryParams,
        Map<String, String> requestHeaders,
        String requestBodyPreview,
        int responseStatus,
        String responseBodyPreview,
        String responseContentType,
        double durationMs,
        boolean unmatched) {
}
