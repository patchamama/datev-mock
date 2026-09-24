package com.elo.datevmock.scoped;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

/**
 * Ports {@code app/scoped_data.py::_seed_for}: a stable SHA256-based seed
 * for a scope key, stable across JVM runs (unlike Java's own salted
 * {@code Object.hashCode()}/{@code String.hashCode()} varying by process in
 * some JDKs) — same scope parts always produce the same seed; different
 * parts (astronomically likely, given SHA256) produce a different one.
 */
class ScopeSeedTest {

    @Test
    void sameScopePartsProduceTheSameSeed() {
        assertEquals(ScopeSeed.seedFor("client-a", "2024"), ScopeSeed.seedFor("client-a", "2024"));
    }

    @Test
    void differentScopePartsProduceDifferentSeeds() {
        assertNotEquals(ScopeSeed.seedFor("client-a", "2024"), ScopeSeed.seedFor("client-b", "2024"));
        assertNotEquals(ScopeSeed.seedFor("client-a", "2024"), ScopeSeed.seedFor("client-a", "2025"));
    }

    @Test
    void partOrderMatters() {
        assertNotEquals(ScopeSeed.seedFor("a", "b"), ScopeSeed.seedFor("b", "a"));
    }
}
