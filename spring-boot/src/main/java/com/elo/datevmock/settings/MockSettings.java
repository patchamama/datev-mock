package com.elo.datevmock.settings;

import org.springframework.stereotype.Component;

import java.util.Set;

/**
 * In-memory port of {@code app/config.py}'s {@code datev_api_version}
 * setting. Persistence (SQLite-backed `settings.json`-equivalent, matching
 * FastAPI's {@code config.save_settings}/{@code load_settings}) is SB4's
 * concern, not SB2's -- this is the shared contract the read/write APIs
 * will consult once they exist.
 */
@Component
public class MockSettings {

    private static final Set<String> VALID_API_VERSIONS = Set.of("legacy", "modern");

    private String datevApiVersion = "legacy";

    public String getDatevApiVersion() {
        return datevApiVersion;
    }

    public void setDatevApiVersion(String value) {
        if (!VALID_API_VERSIONS.contains(value)) {
            throw new IllegalArgumentException(
                    "datev_api_version must be one of " + VALID_API_VERSIONS + ", got: " + value);
        }
        this.datevApiVersion = value;
    }
}
