package com.elo.datevmock.settings;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Ports {@code app/config.py}'s {@code datev_api_version} field: defaults to
 * "legacy" (matching ELO's older reference mock,
 * {@code serve-0.1-generate.jar}), accepts only "legacy"/"modern".
 */
class MockSettingsTest {

    @Test
    void defaultsToLegacy() {
        assertEquals("legacy", new MockSettings().getDatevApiVersion());
    }

    @Test
    void acceptsModern() {
        MockSettings settings = new MockSettings();
        settings.setDatevApiVersion("modern");
        assertEquals("modern", settings.getDatevApiVersion());
    }

    @Test
    void rejectsUnknownValue() {
        MockSettings settings = new MockSettings();
        assertThrows(IllegalArgumentException.class, () -> settings.setDatevApiVersion("bogus"));
    }
}
