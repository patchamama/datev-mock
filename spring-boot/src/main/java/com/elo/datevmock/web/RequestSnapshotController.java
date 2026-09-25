package com.elo.datevmock.web;

import com.elo.datevmock.admin.RequestLogEntry;
import com.elo.datevmock.admin.RequestLogStore;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Resource snapshot export
 * ({@code odd/tasks/datev-mock-resource-snapshot-export.md}): {@code POST
 * /admin/api/snapshots}. Java-side twin of the Python endpoint ({@code
 * app/routers/snapshots.py}) -- see that file's docstring for the full
 * problem statement and design (why the request log's own truncated preview
 * can't be reused directly, and why a self-loopback re-issue is both
 * correct and safe).
 *
 * <h2>Self-loopback safety</h2>
 *
 * <p>This is a plain (non-reactive) {@code @PostMapping} method, exactly the
 * same shape as the already-shipped {@link RelayController}: Tomcat's
 * thread-per-request model means the blocking {@link HttpClient#send}
 * self-loopback call below runs on its own request-handling thread, not
 * shared with the thread serving the inbound request it triggers -- it
 * cannot deadlock waiting on itself.
 *
 * <p>Reuses {@link RelayController}'s own {@link HttpClient} construction
 * pattern (HTTP/1.1 explicitly, no h2c upgrade) rather than a second,
 * differently-configured Java HTTP client for this endpoint.
 */
@RestController
@RequestMapping("/admin/api")
public class RequestSnapshotController {

    private static final Duration SNAPSHOT_TIMEOUT = Duration.ofSeconds(30);

    private final RequestLogStore requestLogStore;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(SNAPSHOT_TIMEOUT)
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    // Repo-relative `snapshots/` (mirrors the Python side's repo-root
    // `snapshots/` -- both gitignored runtime state, see the task doc's
    // scope). Same "plain relative Path" convention this codebase already
    // uses for `datev_mock.db` (StoreConfig) and `settings.json`
    // (MockSettings) -- resolved against the process's working directory
    // (spring-boot/ when run via mvnw.cmd/the packaged jar from there).
    private volatile Path snapshotsRoot = Path.of("snapshots");

    public RequestSnapshotController(RequestLogStore requestLogStore) {
        this.requestLogStore = requestLogStore;
    }

    /** Test-only seam: lets tests point this at a throwaway directory
     * instead of the real repo-relative {@code snapshots/}, the same
     * monkeypatch-style convention the Python side's own test suite uses
     * for its module-level {@code _SNAPSHOTS_ROOT}. */
    void setSnapshotsRootForTesting(Path root) {
        this.snapshotsRoot = root;
    }

    private record Variant(String path, String queryString) {
    }

    private record VariantIdentity(String path, String canonicalQueryString) {
    }

    @PostMapping(value = "/snapshots")
    public Map<String, Object> saveSnapshots(@RequestBody Map<String, Object> body, HttpServletRequest servletRequest)
            throws IOException, InterruptedException {
        Object pathPrefixRaw = body.get("path_prefix");
        if (!(pathPrefixRaw instanceof String pathPrefix) || pathPrefix.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "path_prefix is required");
        }

        String baseUrl = servletRequest.getScheme() + "://" + servletRequest.getServerName() + ":"
                + servletRequest.getServerPort();

        List<String> savedFiles = new ArrayList<>();
        for (Variant variant : distinctGetVariants(pathPrefix)) {
            String target = baseUrl + variant.path();
            if (!variant.queryString().isEmpty()) {
                target = target + "?" + variant.queryString();
            }

            HttpRequest request = HttpRequest.newBuilder(URI.create(target))
                    .timeout(SNAPSHOT_TIMEOUT)
                    .GET()
                    .build();
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());

            String contentType = response.headers().firstValue("content-type").orElse(null);
            String ext = extensionFor(contentType);
            Path filePath = snapshotFilePath(snapshotsRoot, variant.path(), variant.queryString(), ext);
            Files.createDirectories(filePath.getParent());
            Files.write(filePath, response.body());
            savedFiles.add(filePath.toString());
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("saved", savedFiles.size());
        result.put("files", savedFiles);
        return result;
    }

    /** Every canonically distinct (path, queryString) GET combination
     * observed for a resource path/prefix, oldest-first. Ports the Python
     * side's {@code _distinct_get_variants}. Only method/path/queryString
     * from each log entry are read; the (possibly truncated) body preview
     * is never touched. */
    private List<Variant> distinctGetVariants(String pathPrefix) {
        Set<VariantIdentity> seen = new LinkedHashSet<>();
        List<Variant> variants = new ArrayList<>();
        for (RequestLogEntry entry : requestLogStore.getBacklog()) {
            if (!"GET".equals(entry.method())) {
                continue;
            }
            if (!entry.path().startsWith(pathPrefix)) {
                continue;
            }
            String queryString = entry.queryString() == null ? "" : entry.queryString();
            VariantIdentity identity = new VariantIdentity(entry.path(), canonicalQueryString(queryString));
            if (seen.add(identity)) {
                // Preserve the first observed raw query when re-issuing the
                // request. Only the identity (and filename suffix) is
                // canonicalized, so equivalent parameter order cannot inflate
                // `saved` or overwrite the same export twice.
                variants.add(new Variant(entry.path(), queryString));
            }
        }
        return variants;
    }

    /** Content-type decides the extension (see the task doc's scope). */
    static String extensionFor(String contentType) {
        String ct = contentType == null ? "" : contentType.toLowerCase();
        if (ct.contains("xml")) {
            return "xml";
        }
        if (ct.contains("json")) {
            return "json";
        }
        return "txt";
    }

    static Path snapshotFilePath(Path root, String path, String queryString, String ext) {
        String rel = path.startsWith("/") ? path.substring(1) : path;
        return root.resolve(rel + querySuffix(queryString) + "." + ext);
    }

    /** Collapses a query string into a short, safe, collision-resistant
     * filename suffix -- a short hash of the *sorted* query string (so the
     * same params in a different order still land on the same file), empty
     * when there's no query string at all. Mirrors the Python side's
     * {@code _query_suffix} in spirit; the two hashing schemes don't need
     * to (and don't) produce identical digests -- each backend only needs
     * to be internally consistent with itself. */
    static String querySuffix(String queryString) {
        if (queryString == null || queryString.isEmpty()) {
            return "";
        }
        return "__" + sha1Hex(canonicalQueryString(queryString)).substring(0, 10);
    }

    private static String canonicalQueryString(String queryString) {
        if (queryString == null || queryString.isEmpty()) {
            return "";
        }
        String[] parts = queryString.split("&");
        Arrays.sort(parts);
        return String.join("&", parts);
    }

    private static String sha1Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-1");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-1 is a JDK-guaranteed MessageDigest algorithm -- never
            // actually reachable.
            throw new IllegalStateException(e);
        }
    }
}
