package com.elo.datevmock.negotiation;

/**
 * Ports FastAPI's {@code app/routers/accounting.py::_negotiate_format}:
 * an unambiguous {@code Accept} header (exactly one of
 * {@code application/json}/{@code application/xml} present) wins; a missing,
 * wildcard, or ambiguous header falls back to the caller-supplied default
 * (the live {@code default_accounting_format} setting on the FastAPI side).
 */
public final class FormatNegotiator {

    private FormatNegotiator() {
    }

    public static String negotiate(String acceptHeader, String defaultFormat) {
        String accept = acceptHeader == null ? "" : acceptHeader.toLowerCase();
        boolean wantsJson = accept.contains("application/json");
        boolean wantsXml = accept.contains("application/xml");

        if (wantsJson && !wantsXml) {
            return "json";
        }
        if (wantsXml && !wantsJson) {
            return "xml";
        }
        return defaultFormat;
    }
}
