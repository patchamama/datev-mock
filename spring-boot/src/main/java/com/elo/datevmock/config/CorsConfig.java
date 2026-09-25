package com.elo.datevmock.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;

import java.util.List;

/**
 * Ports {@code app/main.py}'s CORS middleware (commit {@code 3f71190}):
 *
 * <pre>{@code
 * app.add_middleware(
 *     CORSMiddleware,
 *     allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
 *     allow_credentials=False,
 *     allow_methods=["*"],
 *     allow_headers=["*"],
 * )
 * }</pre>
 *
 * <p>Spring's {@link CorsConfiguration#setAllowedOriginPatterns} only accepts
 * Ant-style wildcard patterns, not a full regex, so the Python regex's
 * {@code https?://(127.0.0.1|localhost)(:\d+)?} is expanded here into its 8
 * concrete cases (scheme x host x with/without an explicit port) instead of
 * one pattern -- equivalent matching behavior, just enumerated. This lets the
 * SB9 "same frontend, configurable backend URL" admin page (served by
 * FastAPI) call this backend's {@code /admin/api/*} endpoints cross-origin
 * when its configurable API base URL points here.
 *
 * <p>F6 (odd/tasks/datev-mock-standalone-frontend.md) added the literal
 * {@code "null"} origin: a browser sending a request from a
 * {@code file://}-opened page (e.g. {@code frontend/admin.html}
 * double-clicked, or opened by {@code start_java_datev_mock.bat/.sh}'s own
 * post-launch browser-open) sets {@code Origin: null} on its fetch() calls,
 * which none of the concrete host/scheme patterns above can match. Accepted,
 * deliberate local-dev-tool tradeoff, not an oversight -- mirrors the same
 * "null" origin addition made to {@code app/main.py}'s CORS config and the
 * same "real risk, explicitly called out, not over-engineered" pattern
 * already used for F5's relay SSRF note.
 */
@Configuration
public class CorsConfig {

    private static final List<String> ALLOWED_ORIGIN_PATTERNS = List.of(
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1",
            "http://localhost:*",
            "https://localhost:*",
            "http://127.0.0.1:*",
            "https://127.0.0.1:*",
            "null");

    @Bean
    public CorsFilter corsFilter() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOriginPatterns(ALLOWED_ORIGIN_PATTERNS);
        configuration.setAllowCredentials(false);
        configuration.setAllowedMethods(List.of("*"));
        configuration.setAllowedHeaders(List.of("*"));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return new CorsFilter(source);
    }
}
