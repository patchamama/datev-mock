package com.elo.datevmock.negotiation;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Mirrors FastAPI's {@code app/routers/accounting.py::_negotiate_format}:
 * an explicit, unambiguous Accept header wins; otherwise fall back to the
 * live default format setting.
 */
class FormatNegotiatorTest {

    @Test
    void explicitJsonAcceptWinsOverDefault() {
        assertEquals("json", FormatNegotiator.negotiate("application/json", "xml"));
    }

    @Test
    void explicitXmlAcceptWinsOverDefault() {
        assertEquals("xml", FormatNegotiator.negotiate("application/xml", "json"));
    }

    @Test
    void missingAcceptHeaderFallsBackToDefault() {
        assertEquals("xml", FormatNegotiator.negotiate(null, "xml"));
        assertEquals("json", FormatNegotiator.negotiate(null, "json"));
    }

    @Test
    void ambiguousAcceptHeaderRequestingBothFallsBackToDefault() {
        assertEquals(
                "xml",
                FormatNegotiator.negotiate("application/json, application/xml", "xml"));
    }

    @Test
    void wildcardAcceptHeaderFallsBackToDefault() {
        assertEquals("json", FormatNegotiator.negotiate("*/*", "json"));
    }

    @Test
    void acceptHeaderIsCaseInsensitive() {
        assertEquals("json", FormatNegotiator.negotiate("APPLICATION/JSON", "xml"));
    }
}
