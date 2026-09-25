"""Local relay endpoint (F5, `odd/tasks/datev-mock-standalone-frontend.md`):
`POST /admin/api/relay`.

## Problem this solves

The standalone frontend (F1-F4, `frontend/admin.html`) normally calls a
DATEV-compatible target directly from browser JS via `fetch()`. That breaks
for two real, unavoidable browser-platform reasons:

  1. **CORS.** The browser can only read a cross-origin response if the
     *target* sends `Access-Control-Allow-Origin`. This project's own two
     mock backends do; a real DATEV Desktop API almost certainly doesn't,
     and we can't add CORS headers to DATEV's own server.
  2. **NTLM.** Browsers only complete an NTLM challenge/response handshake
     transparently via Integrated Windows Authentication using the OS's own
     logged-in identity -- there is no browser API to hand `fetch()` an
     arbitrary NTLM username/password and have it complete the handshake.

This endpoint is the fix: it runs on this project's own already-running
backend (same-origin/CORS-safe for the browser) and makes the *real*
outbound HTTP call **server-side**, where NTLM and arbitrary hosts are
trivial with a standard HTTP client library, then returns
`{status, headers, body}` for the browser to unwrap.

## Security note (documented, not silently ignored)

This is a generic "make an arbitrary outbound HTTP request" endpoint --
SSRF-shaped by nature (a caller can direct it at any host/port reachable
from this machine, including internal/loopback services). This is accepted
here because this project is a **local developer tool** a person runs
against their own machine/network, not a hosted multi-tenant service where
an SSRF primitive would let one tenant reach another's internal network.
No additional allow-listing/egress restriction has been added -- that would
be over-engineering for this use case, but the risk is real and is called
out here explicitly rather than pretended away.

## Known limitations (documented, not silently skipped)

- Response bodies are always decoded as text (`response.text`, using
  `requests`' own charset detection). Binary response bodies (e.g. a real
  DATEV endpoint returning a non-text payload) are out of scope for this
  pass -- `requests.exceptions` from a body that can't be decoded as text
  are not specially handled beyond the generic error path below.
- NTLM support (`requests-ntlm`) cannot be proven against a real NTLM
  server in this environment (none available) -- see
  `tests/test_relay.py`'s module docstring and the F5 epic write-up for
  exactly what was and wasn't verified end-to-end.
- No request timeout is caller-configurable on this endpoint (unlike F2's
  own connect/read timeout settings, which are a browser-side concept for
  the direct-call path); a fixed server-side timeout is used instead so a
  hung real target can never wedge this process indefinitely.
"""
from __future__ import annotations

from typing import Literal

import requests
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["admin"])

RELAY_ENDPOINT = "/admin/api/relay"

# Fixed server-side ceiling for the outbound call this endpoint makes on the
# caller's behalf. Not caller-configurable in this pass (see module
# docstring) -- generous enough for a real DATEV Desktop API on a local
# network, short enough that a dead/unreachable target can't hang this
# process's worker indefinitely.
_RELAY_TIMEOUT_SECONDS = 30


class RelayAuth(BaseModel):
    type: Literal["none", "basic", "ntlm"] = "none"
    username: str | None = None
    password: str | None = None


class RelayRequest(BaseModel):
    method: str
    url: str
    headers: dict[str, str] | None = None
    body: str | None = None
    auth: RelayAuth | None = None


def _build_requests_auth(auth: RelayAuth | None):
    """Translates the relay's `auth` field into a `requests`-compatible
    `auth=` value. `None`/`"none"` -> no auth. `"basic"` -> `requests`' own
    trivial `(user, pass)` tuple. `"ntlm"` -> `requests_ntlm.HttpNtlmAuth`,
    imported lazily so a missing/broken NTLM dependency never breaks the
    None/Basic paths.
    """
    if auth is None or auth.type == "none":
        return None
    if auth.type == "basic":
        return (auth.username or "", auth.password or "")
    if auth.type == "ntlm":
        from requests_ntlm import HttpNtlmAuth

        return HttpNtlmAuth(auth.username or "", auth.password or "")
    raise ValueError(f"unsupported auth type: {auth.type!r}")


@router.post(RELAY_ENDPOINT)
def relay(payload: RelayRequest) -> dict:
    auth = _build_requests_auth(payload.auth)

    try:
        response = requests.request(
            method=payload.method,
            url=payload.url,
            headers=payload.headers or None,
            data=payload.body,
            auth=auth,
            timeout=_RELAY_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        # A real connection/DNS/timeout/auth-handshake failure against the
        # real target -- surfaced as a clean, structured error, never an
        # unhandled 500. This is also the path a failed NTLM handshake
        # against a non-NTLM (or unreachable) server takes.
        return _error_response(exc)

    return {
        "status": response.status_code,
        "headers": dict(response.headers),
        "body": response.text,
    }


def _error_response(exc: Exception) -> dict:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"error": str(exc)})
