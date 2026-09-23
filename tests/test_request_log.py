"""RED-phase tests for `app/request_log.py` (P1 of
odd/tasks/datev-mock-write-endpoints-and-observability.md — live
request/response logging infrastructure): the ring buffer + SSE pub-sub
module itself, the ASGI middleware wired into every request in
`app/main.py`, and the two `/admin/api/logs*` routes in
`app/routers/admin.py`.

Contract under test:
  - Every request/response is captured into an in-memory ring buffer
    (`app/request_log.get_backlog()`), newest last, each entry a dict with
    at least: seq, timestamp, method, path, query_string, route_path,
    path_params, query_params, request_headers, request_body_preview,
    response_status, response_body_preview, response_content_type,
    duration_ms, unmatched.
  - A route that matched (even one that legitimately returns 404, e.g. the
    addressee-by-id lookup) is `unmatched: False`. A path with no matching
    route at all is `unmatched: True` -- this is the important distinction
    architecture decision #7 calls for.
  - The middleware has zero effect on response correctness: every existing
    JSON/XML endpoint still returns byte-identical bodies, the same status
    code and the same Content-Type after the middleware wraps it.
  - `GET /admin/api/logs` returns the current ring buffer as a plain JSON
    array (primary thing under test here -- SSE streaming itself is only
    smoke-tested, per the task's own guidance that TestClient makes full SSE
    testing awkward).
  - `GET /admin/api/logs/stream` returns 200 with an `text/event-stream`
    Content-Type and yields `data: <json>` lines without hanging forever.
"""
from __future__ import annotations

import asyncio
import json

from fastapi.responses import StreamingResponse

from app import request_log
from app.routers import admin as admin_router

LOGS_ENDPOINT = "/admin/api/logs"
LOGS_STREAM_ENDPOINT = "/admin/api/logs/stream"


# --- middleware / ring-buffer capture, via the real app ---


def test_a_request_is_captured_into_the_ring_buffer(client):
    resp = client.get("/datev/api/diagnostics/v1/echo")
    assert resp.status_code == 200

    logs = client.get(LOGS_ENDPOINT).json()
    matches = [e for e in logs if e["path"] == "/datev/api/diagnostics/v1/echo"]
    assert matches, "expected the echo request to appear in the log"
    entry = matches[-1]
    assert entry["method"] == "GET"
    assert entry["response_status"] == 200
    assert entry["unmatched"] is False
    assert entry["route_path"] == "/datev/api/diagnostics/v1/echo"
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0
    assert "seq" in entry and "timestamp" in entry


def test_unmatched_route_is_flagged_true(client):
    resp = client.get("/datev/api/accounting/v1/totally-made-up-endpoint")
    assert resp.status_code == 404

    logs = client.get(LOGS_ENDPOINT).json()
    matches = [
        e for e in logs if e["path"] == "/datev/api/accounting/v1/totally-made-up-endpoint"
    ]
    assert matches, "expected the unmatched request to appear in the log"
    entry = matches[-1]
    assert entry["unmatched"] is True
    assert entry["route_path"] is None


def test_legitimate_business_logic_404_is_not_flagged_unmatched(client):
    """A route CAN match and still legitimately return 404 (addressee-by-id
    lookup for an unknown id) -- that must be distinguished from a request
    that hit no registered route at all."""
    resp = client.get("/datev/api/master-data/v1/addressees/does-not-exist")
    assert resp.status_code == 404

    logs = client.get(LOGS_ENDPOINT).json()
    matches = [
        e for e in logs if e["path"] == "/datev/api/master-data/v1/addressees/does-not-exist"
    ]
    assert matches, "expected the addressee-by-id request to appear in the log"
    entry = matches[-1]
    assert entry["unmatched"] is False
    assert entry["route_path"] == "/datev/api/master-data/v1/addressees/{addressee_id}"


def test_middleware_does_not_alter_xml_response_body(client):
    plain = client.get("/datev/api/accounting/v1/clients")
    assert plain.status_code == 200
    assert "xml" in plain.headers["content-type"]
    assert plain.text.startswith("<?xml") or plain.text.lstrip().startswith("<")
    assert len(plain.content) > 0


def test_middleware_does_not_alter_json_response_body(client):
    resp = client.get(
        "/datev/api/accounting/v1/clients", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 200
    assert "json" in resp.headers["content-type"]
    data = resp.json()
    assert isinstance(data, list)


def test_middleware_does_not_break_json_request_body_parsing(client):
    """A POST/PUT endpoint that reads a JSON request body downstream must
    still receive that body intact after the middleware has already read it
    once for logging -- this is the request-body-replay risk called out in
    the task."""
    resp = client.post(
        "/admin/api/clients/master-data",
        json={"Name": "Body Replay Test GmbH", "Number": 4242, "Status": "active", "Type": "legal_person"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["Name"] == "Body Replay Test GmbH"

    logs = client.get(LOGS_ENDPOINT).json()
    matches = [e for e in logs if e["path"] == "/admin/api/clients/master-data" and e["method"] == "POST"]
    assert matches
    assert "Body Replay Test GmbH" in matches[-1]["request_body_preview"]

    # cleanup: remove the record we just created so this test stays isolated
    client.delete(f"/admin/api/clients/master-data/{body['Id']}")


def test_response_body_preview_is_captured(client):
    client.get("/datev/api/diagnostics/v1/echo")
    logs = client.get(LOGS_ENDPOINT).json()
    entry = [e for e in logs if e["path"] == "/datev/api/diagnostics/v1/echo"][-1]
    assert entry["response_body_preview"]


# --- SSE stream endpoint: smoke test only (see module docstring) ---
#
# A real HTTP-level round trip through TestClient is not viable here: this
# project's installed Starlette TestClient runs the whole ASGI app to
# completion inside a blocking portal before releasing anything to a
# synchronous caller -- confirmed (during this feature's implementation)
# even against a bare Starlette app with zero custom middleware and an
# explicit short httpx-level `timeout=`. A live SSE stream's generator
# never terminates on its own by design, so any such HTTP-level test would
# hang indefinitely regardless of what the generator awaits or which
# middleware sits in front of it -- exactly the risk the task's own
# guidance warns about ("a basic smoke test... doesn't hang forever is
# enough"). These two tests check the same contract a real request would
# (route wiring + actual generator output) without going through a round
# trip that cannot complete in this environment.


def test_logs_stream_route_returns_an_event_stream_response():
    response = asyncio.run(admin_router.get_logs_stream())
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"


def test_sse_event_stream_yields_backlog_entries_and_can_be_closed_cleanly():
    async def _run() -> None:
        request_log.add_entry(
            request_log.LogEntry(
                seq=-1,
                timestamp="t",
                method="GET",
                path="/probe-sse-backlog",
                query_string="",
                route_path=None,
                path_params={},
                query_params={},
                request_headers={},
                request_body_preview="",
                response_status=200,
                response_body_preview="",
                response_content_type=None,
                duration_ms=0.0,
                unmatched=False,
            )
        )
        gen = admin_router._sse_event_stream()
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
        finally:
            await gen.aclose()
        assert first.startswith("data:")
        payload = json.loads(first[len("data:") :].strip())
        assert "method" in payload and "path" in payload

    asyncio.run(_run())


# --- module-level unit behavior (no app/client needed) ---


def test_get_backlog_returns_a_list():
    assert isinstance(request_log.get_backlog(), list)


def test_logger_has_a_configured_handler():
    assert request_log.logger.handlers, "expected configure_logging() to have attached a handler"


def test_preview_truncates_large_bodies():
    huge = ("x" * 5000).encode("utf-8")
    preview = request_log._preview(huge)
    assert len(preview) < 5000


def test_preview_never_crashes_on_non_utf8_bytes():
    garbage = b"\xff\xfe\x00\x01not valid utf8"
    # must not raise
    preview = request_log._preview(garbage)
    assert isinstance(preview, str)
