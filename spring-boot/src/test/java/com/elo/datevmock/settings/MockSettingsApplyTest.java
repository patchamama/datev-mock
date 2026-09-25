package com.elo.datevmock.settings;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports {@code app/config.py}'s {@code save_settings}/{@code load_settings}
 * persistence contract for the {@code port}/{@code apply()} surface added in
 * SB9 -- not covered by the pre-existing {@link MockSettingsTest}, which only
 * exercises {@code datev_api_version}. {@code settings.json} lives in the
 * working directory (mirroring {@code datev_mock.db}'s SB4 precedent), so
 * every test here deletes it before and after, keeping this from leaking
 * state into {@code MockSettingsTest}'s own "defaults to legacy" assumption
 * or into other tests in the same Maven run.
 *
 * <p><b>Real RED observed</b>: {@code invalidApplyLeavesPreviousSettingsFullyUnchanged}
 * failed against the original {@code apply()} implementation, which called
 * {@code setPort}/{@code setDefaultAccountingFormat}/{@code setDatevApiVersion}
 * in sequence -- a later field's validation failure (e.g. an invalid format)
 * still left an earlier field's new value (the new port) mutated in memory,
 * even though nothing was ever persisted to disk. {@code MockSettings.apply}
 * was fixed to validate all three candidate values before mutating any field,
 * matching FastAPI's atomic construct-a-new-immutable-dataclass-then-swap
 * semantics; this test then passed (GREEN) with no further changes needed.
 */
class MockSettingsApplyTest {

    private static final Path SETTINGS_PATH = Path.of("settings.json");

    @BeforeEach
    @AfterEach
    void cleanSettingsFile() throws IOException {
        Files.deleteIfExists(SETTINGS_PATH);
    }

    @Test
    void applyValidatesAndReportsRestartOnlyOnPortChange() {
        MockSettings settings = new MockSettings();
        int originalPort = settings.getPort();

        boolean restartRequired = settings.apply(originalPort, "json", "modern");
        assertFalse(restartRequired);
        assertEquals("json", settings.getDefaultAccountingFormat());
        assertEquals("modern", settings.getDatevApiVersion());

        boolean restartOnPortChange = settings.apply(originalPort + 1, "json", "modern");
        assertTrue(restartOnPortChange);
        assertEquals(originalPort + 1, settings.getPort());
    }

    @Test
    void invalidApplyLeavesPreviousSettingsFullyUnchanged() {
        MockSettings settings = new MockSettings();
        int originalPort = settings.getPort();
        String originalFormat = settings.getDefaultAccountingFormat();
        String originalApiVersion = settings.getDatevApiVersion();

        assertThrows(IllegalArgumentException.class,
                () -> settings.apply(originalPort + 1, "bogus-format", "modern"));

        assertEquals(originalPort, settings.getPort(), "port must not change when a later field fails validation");
        assertEquals(originalFormat, settings.getDefaultAccountingFormat());
        assertEquals(originalApiVersion, settings.getDatevApiVersion());
        assertFalse(Files.exists(SETTINGS_PATH), "an invalid apply() must never persist settings.json");
    }

    @Test
    void appliedSettingsSurviveAFreshInstanceReload() {
        MockSettings settings = new MockSettings();
        settings.apply(59999, "json", "modern");

        MockSettings reloaded = new MockSettings();
        assertEquals(59999, reloaded.getPort());
        assertEquals("json", reloaded.getDefaultAccountingFormat());
        assertEquals("modern", reloaded.getDatevApiVersion());
    }
}
