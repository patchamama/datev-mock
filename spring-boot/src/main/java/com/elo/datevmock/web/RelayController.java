package com.elo.datevmock.web;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
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
import java.time.Duration;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * F5 local relay ({@code odd/tasks/datev-mock-standalone-frontend.md}):
 * {@code POST /admin/api/relay}. Java-side twin of the Python relay
 * ({@code app/routers/relay.py}) -- see that file's docstring for the full
 * problem statement (CORS + NTLM both being real browser-platform
 * limitations the standalone frontend can't work around client-side).
 *
 * <p>Uses the JDK's own {@link HttpClient} (no new runtime dependency for
 * None/Basic auth) rather than adding a third HTTP client library to this
 * project just for this endpoint.
 *
 * <h2>Security note (documented, not silently ignored)</h2>
 *
 * <p>This is a generic "make an arbitrary outbound HTTP request" endpoint --
 * SSRF-shaped by nature. Accepted here because this is a local developer
 * tool run against the developer's own machine/network, not a hosted
 * multi-tenant service. No egress allow-listing has been added -- that
 * would be over-engineering nobody asked for -- but the risk is real and
 * called out here explicitly.
 *
 * <h2>NTLM: a documented, honest gap (not a silent failure)</h2>
 *
 * <p>Unlike the Python side (which has a mature, drop-in library,
 * {@code requests-ntlm}), a real NTLM handshake is a stateful,
 * connection-pinned challenge/response exchange: the Type 2 challenge and
 * Type 3 response *must* be sent over the exact same TCP connection as the
 * initial Type 1 message, or the server will always reject it. {@link
 * HttpClient} manages its own internal connection pool and gives callers no
 * API to pin two sequential requests to one specific connection, so a
 * correct implementation would need either (a) a raw {@code Socket}-level
 * HTTP/1.1 client written by hand, or (b) Apache HttpClient (4.x, since 5.x
 * dropped built-in NTLM) wired to a real NTLM engine ({@code jcifs-ng}) via
 * its {@code AuthSchemeFactory} SPI -- both a materially larger, riskier
 * change than the rest of this endpoint, and not verifiable end-to-end in
 * this environment (no real NTLM server is available to test against
 * either way). Rather than ship a plausible-looking implementation nobody
 * could prove actually completes a handshake, {@code auth.type == "ntlm"}
 * is rejected here with a clear {@code 501 Not Implemented} and an
 * explanatory message -- an explicit, visible gap, not a silent one. See
 * the F5 epic write-up in {@code odd/tasks/datev-mock-standalone-frontend.md}
 * for the full reasoning; the Python relay's own working {@code
 * requests-ntlm} integration already proves the relay architecture itself
 * (browser -> same-origin backend -> real outbound call) is sound.
 */
@RestController
@RequestMapping("/admin/api")
public class RelayController {

    // Fixed server-side ceiling for the outbound call this endpoint makes
    // on the caller's behalf -- not caller-configurable in this pass (see
    // the Python relay's own docstring for the matching rationale).
    private static final Duration RELAY_TIMEOUT = Duration.ofSeconds(30);

    // HTTP/1.1 explicitly, not the JDK default HTTP/2-with-h2c-upgrade
    // preference: a real DATEV Desktop API (and this project's own two mock
    // backends) are plain HTTP/1.1 servers, and forcing 1.1 avoids a
    // pointless h2c upgrade round-trip/extra headers against a target that
    // will never accept it anyway.
    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(RELAY_TIMEOUT)
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    @PostMapping("/relay")
    public ResponseEntity<Map<String, Object>> relay(@RequestBody RelayRequest request) {
        if (request.method() == null || request.method().isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "method is required");
        }
        if (request.url() == null || request.url().isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "url is required");
        }

        String authType = authType(request.auth());
        if ("ntlm".equals(authType)) {
            return ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED)
                    .body(Map.of("error",
                            "NTLM auth is not implemented on the Java relay backend "
                                    + "(documented gap -- see RelayController's javadoc); "
                                    + "use the Python/FastAPI backend's relay for NTLM targets."));
        }

        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(request.url()))
                    .timeout(RELAY_TIMEOUT);

            if (request.headers() != null) {
                request.headers().forEach(builder::header);
            }
            if ("basic".equals(authType)) {
                builder.header("Authorization", "Basic " + basicCredentials(request.auth()));
            }

            String body = request.body();
            HttpRequest.BodyPublisher publisher = (body == null)
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8);
            builder.method(request.method().toUpperCase(), publisher);

            HttpResponse<String> response =
                    httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("status", response.statusCode());
            Map<String, String> headers = new LinkedHashMap<>();
            response.headers().map().forEach((key, values) -> headers.put(key, String.join(", ", values)));
            result.put("headers", headers);
            result.put("body", response.body());
            return ResponseEntity.ok(result);
        } catch (IllegalArgumentException e) {
            // e.g. a malformed URI -- a caller error, not an upstream one.
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "invalid relay request: " + e.getMessage());
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            // A real connection/DNS/timeout failure against the real
            // target -- surfaced as a clean, structured error, never an
            // unhandled 500.
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(Map.of("error", String.valueOf(e.getMessage())));
        }
    }

    private static String authType(RelayAuth auth) {
        return (auth == null || auth.type() == null) ? "none" : auth.type();
    }

    private static String basicCredentials(RelayAuth auth) {
        String user = auth.username() == null ? "" : auth.username();
        String pass = auth.password() == null ? "" : auth.password();
        return Base64.getEncoder().encodeToString((user + ":" + pass).getBytes(StandardCharsets.UTF_8));
    }
}
