package com.elo.datevmock.admin;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.servlet.HandlerMapping;
import org.springframework.web.util.ContentCachingRequestWrapper;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;

/**
 * Ports {@code app/request_log.py::log_requests_middleware}: one structured
 * {@link RequestLogEntry} per request, feeding {@link RequestLogStore}. A
 * Spring {@code Filter} using {@link ContentCachingRequestWrapper}/
 * {@link ContentCachingResponseWrapper} to capture bodies without breaking
 * the response actually sent to the client -- the idiomatic Spring MVC
 * equivalent of FastAPI's own body-draining-and-rebuilding trick.
 */
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {

    private static final int PREVIEW_LIMIT = 2000;

    private final RequestLogStore store;

    public RequestLoggingFilter(RequestLogStore store) {
        this.store = store;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        // The SSE stream itself never reaches EOF while connected -- wrapping
        // its response would buffer/block indefinitely. Pass it straight
        // through unbuffered, same special case FastAPI's middleware makes
        // by Content-Type (this filter instead recognizes it by path, since
        // that's known upfront here).
        if (request.getRequestURI().equals("/admin/api/logs/stream")) {
            long start = System.nanoTime();
            chain.doFilter(request, response);
            logEntry(request, response, start, "", "(streaming response - body not captured)",
                    "text/event-stream");
            return;
        }

        ContentCachingRequestWrapper wrappedRequest = new ContentCachingRequestWrapper(request);
        ContentCachingResponseWrapper wrappedResponse = new ContentCachingResponseWrapper(response);
        long start = System.nanoTime();
        try {
            chain.doFilter(wrappedRequest, wrappedResponse);
        } finally {
            String requestBody = preview(wrappedRequest.getContentAsByteArray());
            String responseBody = preview(wrappedResponse.getContentAsByteArray());
            logEntry(wrappedRequest, wrappedResponse, start, requestBody, responseBody,
                    wrappedResponse.getContentType());
            wrappedResponse.copyBodyToResponse();
        }
    }

    private void logEntry(HttpServletRequest request, HttpServletResponse response, long startNanos,
            String requestBodyPreview, String responseBodyPreview, String responseContentType) {
        double durationMs = (System.nanoTime() - startNanos) / 1_000_000.0;
        Object bestMatchingPattern = request.getAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE);
        boolean unmatched = bestMatchingPattern == null;

        RequestLogEntry entry = new RequestLogEntry(
                store.nextSeq(),
                Instant.now().toString(),
                request.getMethod(),
                request.getRequestURI(),
                request.getQueryString() == null ? "" : request.getQueryString(),
                bestMatchingPattern == null ? null : bestMatchingPattern.toString(),
                pathParams(request),
                queryParams(request),
                headersOfInterest(request),
                requestBodyPreview,
                response.getStatus(),
                responseBodyPreview,
                responseContentType,
                durationMs,
                unmatched);
        store.addEntry(entry);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> pathParams(HttpServletRequest request) {
        Object raw = request.getAttribute(HandlerMapping.URI_TEMPLATE_VARIABLES_ATTRIBUTE);
        if (raw instanceof Map<?, ?> map) {
            Map<String, String> result = new LinkedHashMap<>();
            map.forEach((k, v) -> result.put(String.valueOf(k), String.valueOf(v)));
            return result;
        }
        return Map.of();
    }

    private static Map<String, String> queryParams(HttpServletRequest request) {
        Map<String, String> result = new TreeMap<>();
        request.getParameterMap().forEach((name, values) -> {
            if (values.length > 0) {
                result.put(name, values[0]);
            }
        });
        return result;
    }

    private static Map<String, String> headersOfInterest(HttpServletRequest request) {
        Map<String, String> result = new LinkedHashMap<>();
        for (String name : new String[] {"accept", "content-type"}) {
            String value = request.getHeader(name);
            if (value != null) {
                result.put(name, value);
            }
        }
        return result;
    }

    private static String preview(byte[] raw) {
        if (raw == null || raw.length == 0) {
            return "";
        }
        String text = new String(raw, StandardCharsets.UTF_8);
        if (text.length() > PREVIEW_LIMIT) {
            return text.substring(0, PREVIEW_LIMIT) + "... (truncated, " + text.length() + " chars total)";
        }
        return text;
    }
}
