package com.elo.datevmock.web;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * RED-then-GREEN tests for the resource snapshot export endpoint ({@code
 * POST /admin/api/snapshots}, {@link RequestSnapshotController}) -- Java
 * twin of {@code tests/test_snapshots.py}. See
 * {@code odd/tasks/datev-mock-resource-snapshot-export.md} for the full
 * design.
 *
 * <h2>Why a real running server, not {@code MockMvc}</h2>
 *
 * <p>The endpoint's whole point is a genuine *self-loopback* HTTP call: it
 * reads the incoming request's own scheme/server-name/port and issues a
 * real {@link java.net.http.HttpClient} request back at itself to get a
 * fresh, complete response body. {@code MockMvc} (used by {@link
 * RelayControllerTest} for the *outbound-only* relay, where the "target" is
 * an unrelated local {@code HttpServer}) never binds a real socket for
 * *this* application, so a self-loopback call through it would try to
 * connect to a host:port nothing is actually listening on. This test class
 * instead uses {@code @SpringBootTest(webEnvironment = RANDOM_PORT)} --a
 * real embedded Tomcat on a real ephemeral port-- and drives it end-to-end
 * with {@link TestRestTemplate}: the initiating POST *and* the
 * self-loopback GET it triggers both go over a real socket, proving the
 * design's own safety argument (a blocking outbound call from a
 * thread-per-request handler doesn't deadlock on itself) rather than
 * assuming it.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class RequestSnapshotControllerTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private RequestSnapshotController controller;

    @TempDir
    Path tempDir;

    @BeforeEach
    void pointSnapshotsAtAThrowawayDirectory() {
        // Never the real repo-relative `snapshots/` -- a fresh JUnit
        // @TempDir per test, auto-cleaned afterward.
        controller.setSnapshotsRootForTesting(tempDir.resolve("snapshots"));
    }

    private String baseUrl() {
        return "http://localhost:" + port;
    }

    // --- full, untruncated content (the real bug this design avoids) ---

    @Test
    void savesFullUntruncatedContentNotAStaleOrTruncatedCopy() throws IOException {
        // A real GET, big enough to exceed RequestLoggingFilter's own
        // PREVIEW_LIMIT (2000 chars) -- this mock's master-data/clients XML
        // is tens of KB. Explicit `Accept: application/xml` so this
        // comparison call negotiates the same representation the
        // controller's own self-loopback call gets (a bare
        // java.net.http.HttpClient request with no Accept header at all) --
        // TestRestTemplate's default byte[] Accept header otherwise
        // advertises JSON ahead of XML and would compare two genuinely
        // different (both valid, neither truncated) representations.
        HttpHeaders xmlAccept = new HttpHeaders();
        xmlAccept.setAccept(List.of(MediaType.APPLICATION_XML));
        ResponseEntity<byte[]> direct = restTemplate.exchange(
                baseUrl() + "/datev/api/master-data/v1/clients",
                HttpMethod.GET,
                new HttpEntity<>(xmlAccept),
                byte[].class);
        assertThat(direct.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(direct.getBody().length).isGreaterThan(4000);

        Map<String, Object> result = postSnapshots("/datev/api/master-data/v1/clients");
        assertThat(((Number) result.get("saved")).intValue()).isGreaterThanOrEqualTo(1);

        Path savedFile = tempDir.resolve("snapshots").resolve("datev/api/master-data/v1/clients.xml");
        assertThat(Files.exists(savedFile)).isTrue();
        byte[] savedBytes = Files.readAllBytes(savedFile);

        // Exact byte-for-byte match with a real, independent GET -- not
        // truncated, not stale.
        assertThat(savedBytes).hasSize(direct.getBody().length);
        assertThat(savedBytes).isEqualTo(direct.getBody());
        @SuppressWarnings("unchecked")
        List<String> files = (List<String>) result.get("files");
        assertThat(files).contains(savedFile.toString());
    }

    // --- distinct query-string variants: real deduplication ---

    @Test
    void distinctQueryStringVariantsEachProduceTheirOwnFile() throws IOException {
        // `/datev/api/master-data/v1/banks` has no nested "by id" GET route
        // (unlike addressees/employees), and RequestLogStore is a
        // process-wide singleton shared across the whole Spring test
        // context -- a resource with no children keeps this test's
        // path_prefix match set under our own control instead of also
        // picking up unrelated history from other test classes sharing the
        // same cached application context.
        ResponseEntity<byte[]> r1a =
                restTemplate.getForEntity(baseUrl() + "/datev/api/master-data/v1/banks?marker=alpha", byte[].class);
        ResponseEntity<byte[]> r1b =
                restTemplate.getForEntity(baseUrl() + "/datev/api/master-data/v1/banks?marker=alpha", byte[].class);
        ResponseEntity<byte[]> r2 =
                restTemplate.getForEntity(baseUrl() + "/datev/api/master-data/v1/banks?marker=beta", byte[].class);
        assertThat(r1a.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(r1b.getStatusCode().is2xxSuccessful()).isTrue();
        assertThat(r2.getStatusCode().is2xxSuccessful()).isTrue();

        Map<String, Object> result = postSnapshots("/datev/api/master-data/v1/banks");

        // At least our 2 distinct combos were saved (other test classes may
        // also have exercised this same plain, no-query endpoint -- that's
        // a 3rd, legitimate, harmless variant this assertion tolerates).
        assertThat(((Number) result.get("saved")).intValue()).isGreaterThanOrEqualTo(2);

        Path banksDir = tempDir.resolve("snapshots").resolve("datev/api/master-data/v1");
        Path expectedAlpha = banksDir.resolve("banks" + RequestSnapshotController.querySuffix("marker=alpha") + ".json");
        Path expectedBeta = banksDir.resolve("banks" + RequestSnapshotController.querySuffix("marker=beta") + ".json");

        // Exactly one file per distinct query -- the duplicate
        // "marker=alpha" call did NOT produce a second, differently-named
        // file.
        assertThat(Files.exists(expectedAlpha)).isTrue();
        assertThat(Files.exists(expectedBeta)).isTrue();
        assertThat(expectedAlpha).isNotEqualTo(expectedBeta);

        // Both real, complete, non-empty JSON content -- not a stub.
        for (Path f : List.of(expectedAlpha, expectedBeta)) {
            byte[] content = Files.readAllBytes(f);
            assertThat(content.length).isGreaterThan(0);
            assertThat(content).isEqualTo(r1a.getBody()); // this mock ignores query params, same body
        }
    }

    // --- no observed requests yet: sane empty result, not an error ---

    @Test
    void noObservedRequestsReturnsSaneEmptyResultNotAnError() {
        Map<String, Object> result = postSnapshots("/datev/api/never-requested-resource-xyz");
        assertThat(((Number) result.get("saved")).intValue()).isEqualTo(0);
        assertThat((List<?>) result.get("files")).isEmpty();
    }

    @Test
    void reorderedQueryVariantsExportOnceWithoutOverwritingOrInflatingSaved() {
        String path = "/datev/api/snapshot-dedup-test";

        // This deliberately unknown, unique path avoids interference from
        // the process-wide request-log history shared by other tests. The
        // exact saved count therefore proves canonical query deduplication,
        // rather than merely a filename collision after two exports.
        ResponseEntity<String> first = restTemplate.getForEntity(baseUrl() + path + "?b=2&a=1", String.class);
        ResponseEntity<String> second = restTemplate.getForEntity(baseUrl() + path + "?a=1&b=2", String.class);
        assertThat(first.getStatusCode().value()).isEqualTo(404);
        assertThat(second.getStatusCode().value()).isEqualTo(404);

        Map<String, Object> result = postSnapshots(path);

        assertThat(((Number) result.get("saved")).intValue()).isEqualTo(1);
        assertThat((List<?>) result.get("files")).hasSize(1);
    }

    // --- content-type decides the extension ---

    @Test
    void xmlAndJsonResourcesGetTheRightExtension() throws IOException {
        // Diagnostics echo and DMS documents are both leaf resources (no
        // nested GET children) -- unlike
        // "/datev/api/accounting/v1/clients", which is also a *prefix* of
        // many real, deeply-nested fiscal-year sub-resources other test
        // classes exercise against this same shared request log.
        restTemplate.getForEntity(baseUrl() + "/datev/api/diagnostics/v1/echo", String.class); // XML by default
        restTemplate.getForEntity(baseUrl() + "/datev/api/dms/v1/documents", String.class); // JSON-only

        Map<String, Object> echoResult = postSnapshots("/datev/api/diagnostics/v1/echo");
        assertThat(((Number) echoResult.get("saved")).intValue()).isEqualTo(1);
        assertThat(Files.exists(tempDir.resolve("snapshots").resolve("datev/api/diagnostics/v1/echo.xml"))).isTrue();

        Map<String, Object> documentsResult = postSnapshots("/datev/api/dms/v1/documents");
        assertThat(((Number) documentsResult.get("saved")).intValue()).isEqualTo(1);
        assertThat(Files.exists(tempDir.resolve("snapshots").resolve("datev/api/dms/v1/documents.json"))).isTrue();
    }

    // --- module-level unit behavior (no live server needed) ---

    @Test
    void querySuffixIsEmptyForNoQueryString() {
        assertThat(RequestSnapshotController.querySuffix("")).isEmpty();
        assertThat(RequestSnapshotController.querySuffix(null)).isEmpty();
    }

    @Test
    void querySuffixIsStableRegardlessOfParamOrder() {
        String a = RequestSnapshotController.querySuffix("b=2&a=1");
        String b = RequestSnapshotController.querySuffix("a=1&b=2");
        assertThat(a).isEqualTo(b);
        assertThat(a).startsWith("__");
    }

    @Test
    void querySuffixDiffersForDifferentQueryContent() {
        assertThat(RequestSnapshotController.querySuffix("a=1"))
                .isNotEqualTo(RequestSnapshotController.querySuffix("a=2"));
    }

    @Test
    void extensionForPrefersXmlOverJsonWhenBothMentioned() {
        assertThat(RequestSnapshotController.extensionFor("application/xml; charset=utf-8")).isEqualTo("xml");
        assertThat(RequestSnapshotController.extensionFor("application/json")).isEqualTo("json");
        assertThat(RequestSnapshotController.extensionFor(null)).isEqualTo("txt");
        assertThat(RequestSnapshotController.extensionFor("text/plain")).isEqualTo("txt");
    }

    @Test
    void rejectsAMissingPathPrefix() {
        ResponseEntity<Map> resp = restTemplate.postForEntity(
                baseUrl() + "/admin/api/snapshots", Map.of(), Map.class);
        assertThat(resp.getStatusCode().is4xxClientError()).isTrue();
    }

    @Test
    void rejectsAnEmptyOrWhitespaceOnlyPathPrefix() {
        for (String pathPrefix : List.of("", "   ")) {
            ResponseEntity<Map> response = restTemplate.postForEntity(
                    baseUrl() + "/admin/api/snapshots", Map.of("path_prefix", pathPrefix), Map.class);
            assertThat(response.getStatusCode().value()).isEqualTo(422);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> postSnapshots(String pathPrefix) {
        ResponseEntity<Map> resp = restTemplate.postForEntity(
                baseUrl() + "/admin/api/snapshots", Map.of("path_prefix", pathPrefix), Map.class);
        assertThat(resp.getStatusCode().is2xxSuccessful()).isTrue();
        return (Map<String, Object>) resp.getBody();
    }
}
