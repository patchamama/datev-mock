package com.elo.datevmock.scoped;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.stream.Collectors;

/**
 * Ports {@code app/scoped_data.py::_seed_for}: a stable SHA256-based seed
 * for a scope key. Stable and reproducible for the same input, unlike a
 * bare {@code Object.hashCode()} — parity with the underlying property that
 * matters (a real, deterministic function of the scope parts), not with
 * Python's exact hex-slice-to-int conversion, since neither JVM's
 * {@link java.util.Random} nor CPython's Mersenne Twister accept the same
 * seed format anyway (see {@link ScopedDataService} for why byte-identical
 * generated values were never a goal for this port).
 */
final class ScopeSeed {

    private ScopeSeed() {
    }

    static long seedFor(String... parts) {
        String joined = Arrays.stream(parts).collect(Collectors.joining("|"));
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(joined.getBytes(StandardCharsets.UTF_8));
            long seed = 0L;
            for (int i = 0; i < 8; i++) {
                seed = (seed << 8) | (hash[i] & 0xFF);
            }
            return seed;
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 must be available on every JVM", e);
        }
    }
}
