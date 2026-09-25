package com.elo.datevmock.web;

/**
 * Ports the Python relay's {@code RelayAuth} Pydantic model
 * ({@code app/routers/relay.py}). {@code type} is one of {@code "none"}
 * (default), {@code "basic"}, or {@code "ntlm"} -- validated by
 * {@link RelayController}, not here, to keep this a plain data holder
 * matching this codebase's existing {@code @RequestBody Map}/record style
 * for admin JSON payloads.
 */
public record RelayAuth(String type, String username, String password) {
}
