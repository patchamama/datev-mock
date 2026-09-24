package com.elo.datevmock.overrides;

import java.time.Instant;

/**
 * Ports {@code app/overrides.py::Override}. A plain mutable holder (not a
 * record) because {@code enabled} is flipped in place by
 * {@link OverrideStore#setEnabled} — matches the Python dataclass's own
 * mutability. Named {@code OverrideEntry} rather than {@code Override} to
 * avoid any reader confusion with {@code java.lang.Override} (same-package
 * resolution would make the bare name work either way, but the distinct
 * name is clearer).
 */
public final class OverrideEntry {

    private final String content;
    private final String contentType;
    private final String filename;
    private final String uploadedAt;
    private boolean enabled;

    OverrideEntry(String content, String contentType, String filename, String uploadedAt, boolean enabled) {
        this.content = content;
        this.contentType = contentType;
        this.filename = filename;
        this.uploadedAt = uploadedAt;
        this.enabled = enabled;
    }

    public String content() {
        return content;
    }

    public String contentType() {
        return contentType;
    }

    String filename() {
        return filename;
    }

    String uploadedAt() {
        return uploadedAt;
    }

    boolean enabled() {
        return enabled;
    }

    void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    static String nowIso() {
        return Instant.now().toString();
    }
}
