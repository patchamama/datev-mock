package com.elo.datevmock.settings;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Ports {@code app/config.py}'s {@code Settings} dataclass, including
 * {@code port} and JSON persistence to a gitignored {@code settings.json}
 * in the working directory (mirroring FastAPI's own
 * {@code load_settings}/{@code save_settings} convention, and this
 * project's {@code datev_mock.db} same-directory precedent from SB4).
 */
@Component
public class MockSettings {

    private static final Set<String> VALID_API_VERSIONS = Set.of("legacy", "modern");
    private static final Set<String> VALID_FORMATS = Set.of("xml", "json");
    private static final Path SETTINGS_PATH = Path.of("settings.json");
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private int port = 58553;
    private String defaultAccountingFormat = "xml";
    private String datevApiVersion = "legacy";

    public MockSettings() {
        load();
    }

    public synchronized int getPort() {
        return port;
    }

    public synchronized void setPort(int value) {
        validatePort(value);
        this.port = value;
    }

    public synchronized String getDatevApiVersion() {
        return datevApiVersion;
    }

    public synchronized void setDatevApiVersion(String value) {
        validateApiVersion(value);
        this.datevApiVersion = value;
    }

    /** Ports {@code app/config.py}'s {@code default_accounting_format} (default {@code "xml"}). */
    public synchronized String getDefaultAccountingFormat() {
        return defaultAccountingFormat;
    }

    public synchronized void setDefaultAccountingFormat(String value) {
        validateFormat(value);
        this.defaultAccountingFormat = value;
    }

    /**
     * Applies and persists a full settings update, mirroring
     * {@code app/config.py::save_settings}, which constructs a brand-new
     * immutable {@code Settings} dataclass and only swaps it in once every
     * field has validated together -- an invalid field leaves the previous
     * settings completely untouched.
     *
     * <p>Every candidate value is validated first, with no field mutated yet
     * (unlike an earlier version of this method, which called the individual
     * setters in sequence and could leave an earlier field's new value
     * applied in memory even though a later field's validation failure meant
     * nothing was persisted -- caught by
     * {@code MockSettingsApplyTest::invalidApplyLeavesPreviousSettingsFullyUnchanged}).
     * Only after all three pass are they committed together, then persisted.
     *
     * @return whether the port actually changed (FastAPI's
     *         {@code restart_required} flag -- this mock never live-rebinds
     *         its embedded server either, same as FastAPI's own uvicorn).
     */
    public synchronized boolean apply(int newPort, String newFormat, String newApiVersion) {
        validatePort(newPort);
        validateFormat(newFormat);
        validateApiVersion(newApiVersion);

        boolean restartRequired = newPort != this.port;
        this.port = newPort;
        this.defaultAccountingFormat = newFormat;
        this.datevApiVersion = newApiVersion;
        save();
        return restartRequired;
    }

    private static void validatePort(int value) {
        if (value < 1 || value > 65535) {
            throw new IllegalArgumentException("port must be between 1 and 65535, got: " + value);
        }
    }

    private static void validateApiVersion(String value) {
        if (!VALID_API_VERSIONS.contains(value)) {
            throw new IllegalArgumentException(
                    "datev_api_version must be one of " + VALID_API_VERSIONS + ", got: " + value);
        }
    }

    private static void validateFormat(String value) {
        if (!VALID_FORMATS.contains(value)) {
            throw new IllegalArgumentException(
                    "default_accounting_format must be one of " + VALID_FORMATS + ", got: " + value);
        }
    }

    private synchronized void load() {
        if (!Files.exists(SETTINGS_PATH)) {
            return;
        }
        try {
            Map<?, ?> data = MAPPER.readValue(SETTINGS_PATH.toFile(), Map.class);
            if (data.get("port") instanceof Number n) {
                port = n.intValue();
            }
            if (data.get("default_accounting_format") instanceof String s) {
                defaultAccountingFormat = s;
            }
            if (data.get("datev_api_version") instanceof String s) {
                datevApiVersion = s;
            }
        } catch (IOException e) {
            // Corrupt/unreadable settings.json: fall back to defaults rather
            // than fail startup, matching FastAPI's own lenient load path.
        }
    }

    private synchronized void save() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("port", port);
        data.put("default_accounting_format", defaultAccountingFormat);
        data.put("datev_api_version", datevApiVersion);
        try {
            MAPPER.writeValue(SETTINGS_PATH.toFile(), data);
        } catch (IOException e) {
            throw new IllegalStateException("failed to persist settings.json", e);
        }
    }
}
