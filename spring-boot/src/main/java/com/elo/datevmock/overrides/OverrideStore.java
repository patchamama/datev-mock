package com.elo.datevmock.overrides;

import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/**
 * Ports the storage layer of {@code app/overrides.py}: an in-memory,
 * process-lifetime store of endpoint-response overrides an admin/test
 * caller uploads to be served verbatim instead of this mock's normal
 * generated response for a specific endpoint key.
 *
 * <p>Deliberately excludes {@code detect_candidates}/{@code detect_content_type}/
 * {@code sanitize_xml} (upload-time XML-root/JSON-fingerprint detection
 * across every DATEV resource type) and any router/multipart-upload
 * wiring — those belong to SB9, whose own scope explicitly names "multipart
 * `file` override upload/resolve/list/update/delete". This store is the
 * shared state layer SB9's router will sit on top of; a caller here already
 * knows the resolved endpoint key(s), exactly like FastAPI's own storage
 * function signatures ({@code set_override(key, ...)}) do.
 */
@Component
public class OverrideStore {

    private final ConcurrentMap<String, OverrideEntry> overrides = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, PendingUpload> pending = new ConcurrentHashMap<>();

    public void setOverride(String key, String content, String contentType, String filename) {
        overrides.put(key, new OverrideEntry(content, contentType, filename, OverrideEntry.nowIso(), true));
    }

    public OverrideEntry getActiveOverride(String key) {
        OverrideEntry entry = overrides.get(key);
        return entry != null && entry.enabled() ? entry : null;
    }

    public Map<String, OverrideEntry> listOverrides() {
        return Map.copyOf(overrides);
    }

    public void setEnabled(String key, boolean enabled) {
        OverrideEntry entry = overrides.get(key);
        if (entry != null) {
            entry.setEnabled(enabled);
        }
    }

    public void deleteOverride(String key) {
        overrides.remove(key);
    }

    public void clearAllOverrides() {
        overrides.clear();
        pending.clear();
    }

    public String storePending(String content, String contentType, String filename, List<String> candidates) {
        String pendingId = UUID.randomUUID().toString();
        pending.put(pendingId, new PendingUpload(content, contentType, filename, List.copyOf(candidates)));
        return pendingId;
    }

    public void resolvePending(String pendingId, String key) {
        PendingUpload upload = pending.get(pendingId);
        if (upload == null) {
            throw new IllegalArgumentException("unknown pending upload: " + pendingId);
        }
        if (!upload.candidates().contains(key)) {
            throw new IllegalArgumentException(
                    "'" + key + "' is not one of the candidates for pending upload '" + pendingId + "'");
        }
        setOverride(key, upload.content(), upload.contentType(), upload.filename());
        pending.remove(pendingId);
    }

    private record PendingUpload(String content, String contentType, String filename, List<String> candidates) {
    }
}
