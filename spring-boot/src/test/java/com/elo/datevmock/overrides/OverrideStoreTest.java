package com.elo.datevmock.overrides;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports {@code app/overrides.py}'s in-memory endpoint-response override
 * storage: an admin/test-uploaded response served verbatim in place of the
 * normal generated one for a specific endpoint key. Only the storage layer
 * is ported here (set/get/list/enable/delete/clear + the pending-upload
 * flow for ambiguous fingerprint matches) — upload-time content detection
 * (XML root tag / JSON field fingerprinting across every DATEV resource
 * type) and router wiring belong to SB9 ("multipart file override
 * upload/resolve/list/update/delete" is explicitly SB9's scope), so this
 * store is exercised directly with endpoint keys/content a caller already
 * decided on, exactly as FastAPI's own {@code test_overrides.py}-style
 * storage tests would.
 */
class OverrideStoreTest {

    private final OverrideStore store = new OverrideStore();

    @Test
    void noOverrideByDefault() {
        assertNull(store.getActiveOverride("accounting.clients"));
    }

    @Test
    void setOverrideMakesItActive() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");

        OverrideEntry active = store.getActiveOverride("accounting.clients");
        assertEquals("<ArrayOfClient/>", active.content());
        assertEquals("xml", active.contentType());
        assertEquals("clients.xml", active.filename());
        assertTrue(active.enabled());
    }

    @Test
    void disablingAnOverrideMakesItInactiveButKeepsItStored() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");
        store.setEnabled("accounting.clients", false);

        assertNull(store.getActiveOverride("accounting.clients"));
        assertFalse(store.listOverrides().get("accounting.clients").enabled());
    }

    @Test
    void reEnablingMakesItActiveAgain() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");
        store.setEnabled("accounting.clients", false);
        store.setEnabled("accounting.clients", true);

        assertTrue(store.getActiveOverride("accounting.clients") != null);
    }

    @Test
    void deletingRemovesItEntirely() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");
        store.deleteOverride("accounting.clients");

        assertNull(store.getActiveOverride("accounting.clients"));
        assertTrue(store.listOverrides().isEmpty());
    }

    @Test
    void listOverridesReturnsMetadataForEveryStoredKey() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");
        store.setOverride("diagnostics.echo", "{}", "json", "echo.json");

        Map<String, OverrideEntry> all = store.listOverrides();
        assertEquals(2, all.size());
        assertTrue(all.containsKey("accounting.clients"));
        assertTrue(all.containsKey("diagnostics.echo"));
    }

    @Test
    void clearAllOverridesWipesEverything() {
        store.setOverride("accounting.clients", "<ArrayOfClient/>", "xml", "clients.xml");
        String pendingId = store.storePending("{}", "json", "ambiguous.json", List.of("a", "b"));

        store.clearAllOverrides();

        assertTrue(store.listOverrides().isEmpty());
        assertThrows(IllegalArgumentException.class, () -> store.resolvePending(pendingId, "a"));
    }

    @Test
    void pendingUploadResolvesToAStoredOverrideForTheChosenCandidateKey() {
        String pendingId = store.storePending(
                "{\"id\":\"1\"}", "json", "ambiguous.json", List.of("accounting.creditors", "accounting.debitors"));

        store.resolvePending(pendingId, "accounting.debitors");

        OverrideEntry active = store.getActiveOverride("accounting.debitors");
        assertEquals("{\"id\":\"1\"}", active.content());
        assertNull(store.getActiveOverride("accounting.creditors"));
    }

    @Test
    void resolvingAPendingUploadWithANonCandidateKeyThrows() {
        String pendingId = store.storePending(
                "{\"id\":\"1\"}", "json", "ambiguous.json", List.of("accounting.creditors"));

        assertThrows(IllegalArgumentException.class,
                () -> store.resolvePending(pendingId, "accounting.debitors"));
    }

    @Test
    void resolvingAnUnknownPendingIdThrows() {
        assertThrows(IllegalArgumentException.class, () -> store.resolvePending("no-such-id", "accounting.clients"));
    }

    @Test
    void resolvingConsumesThePendingUpload() {
        String pendingId = store.storePending("{}", "json", "f.json", List.of("accounting.clients"));
        store.resolvePending(pendingId, "accounting.clients");

        assertThrows(IllegalArgumentException.class,
                () -> store.resolvePending(pendingId, "accounting.clients"));
    }
}
