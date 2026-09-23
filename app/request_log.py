"""In-process pub-sub + ring buffer for live request/response observability.

See `odd/tasks/datev-mock-write-endpoints-and-observability.md`, Architecture
decisions #6/#7 (P1 of that feature). This module is the whole "live
request/response log":

  - a bounded ring buffer of the last ~1000 request/response log entries
    (`get_backlog()`), consumed by `GET /admin/api/logs`;
  - broadcast of each new entry to any connected SSE client
    (`register_subscriber()`/`unregister_subscriber()`), consumed by
    `GET /admin/api/logs/stream` in `app/routers/admin.py`;
  - one structured line per request on a dedicated `logging` logger, in
    *addition* to (not instead of) uvicorn's own access log;
  - unmatched-route detection: a request whose routing never resolved to a
    registered FastAPI/Starlette route (`request.scope["route"] is None`
    after `call_next` returns), distinct from an intentional business-logic
    404 like `GET /master-data/v1/addressees/{id}` for an unknown id, where
    a route DID match and the endpoint itself chose to return 404.

`log_requests_middleware` is the actual ASGI HTTP middleware, wired into
every request via `app.middleware("http")` in `app/main.py`.
"""
from __future__ import annotations

import asyncio
import dataclasses
import itertools
import logging
from collections import deque
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("datev_mock.requests")

_BUFFER_SIZE = 1000
_PREVIEW_LIMIT = 2000
_SUBSCRIBER_QUEUE_SIZE = 200
_REQUEST_HEADERS_OF_INTEREST = ("accept", "content-type")

_buffer: "deque[dict[str, Any]]" = deque(maxlen=_BUFFER_SIZE)
_subscribers: "set[asyncio.Queue[dict[str, Any]]]" = set()
_seq_counter = itertools.count(1)


@dataclasses.dataclass
class LogEntry:
    seq: int
    timestamp: str
    method: str
    path: str
    query_string: str
    route_path: str | None
    path_params: dict[str, Any]
    query_params: dict[str, Any]
    request_headers: dict[str, str]
    request_body_preview: str
    response_status: int
    response_body_preview: str
    response_content_type: str | None
    duration_ms: float
    unmatched: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a stdout handler to this module's logger, once.

    Deliberately separate from uvicorn's own access-log setup (left
    untouched) -- this is an additional, more detailed line per request, not
    a replacement. Idempotent: calling it more than once (e.g. because this
    module gets imported by both `app/main.py` and test modules) only
    attaches the handler the first time.
    """
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


# Configured at import time (not lazily inside the lifespan) so CLI logging
# is active for any test or script that imports this module directly,
# regardless of whether the app's lifespan ever runs (e.g. a bare
# `TestClient(app)` without entering it as a context manager).
configure_logging()


def _preview(raw: bytes) -> str:
    """First ~2000 chars of `raw`, decoded permissively. Never raises --
    non-JSON, non-UTF-8 or huge bodies all degrade gracefully instead of
    crashing the middleware for every request behind them."""
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="replace")
    if len(text) > _PREVIEW_LIMIT:
        return text[:_PREVIEW_LIMIT] + f"... (truncated, {len(text)} chars total)"
    return text


def _headers_of_interest(headers: Any) -> dict[str, str]:
    return {name: headers[name] for name in _REQUEST_HEADERS_OF_INTEREST if name in headers}


def register_subscriber() -> "asyncio.Queue[dict[str, Any]]":
    queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
    _subscribers.add(queue)
    return queue


def unregister_subscriber(queue: "asyncio.Queue[dict[str, Any]]") -> None:
    _subscribers.discard(queue)


def get_backlog(limit: int = _BUFFER_SIZE) -> list[dict[str, Any]]:
    """The current ring buffer, oldest first. `GET /admin/api/logs` and a
    fresh SSE client's initial backlog dump both use this directly."""
    entries = list(_buffer)
    if limit < len(entries):
        return entries[-limit:]
    return entries


def _broadcast(entry: dict[str, Any]) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait(entry)
        except asyncio.QueueFull:
            # Slow/disconnected client: drop this entry for it rather than
            # blocking every request in the whole app on one stuck consumer.
            continue


def _log_to_cli(entry: dict[str, Any]) -> None:
    marker = " [UNMATCHED]" if entry["unmatched"] else ""
    line = (
        f"{entry['method']} {entry['path']} -> "
        f"{entry['response_status']} ({entry['duration_ms']:.1f}ms){marker}"
    )
    logger.log(logging.WARNING if entry["unmatched"] else logging.INFO, line)


def add_entry(entry: LogEntry) -> dict[str, Any]:
    data = entry.to_dict()
    _buffer.append(data)
    _broadcast(data)
    _log_to_cli(data)
    return data


async def log_requests_middleware(request: Request, call_next: Any) -> Response:
    start = perf_counter()

    # This project's installed Starlette wraps the middleware-visible
    # `request` in `_CachedRequest`: once `await request.body()` has been
    # called, its internal `wrapped_receive()` transparently replays that
    # cached body to whatever runs downstream (`call_next`) and then falls
    # back to normal disconnect-listening behavior afterward -- no manual
    # ASGI receive-patching needed here, reading the body once is enough to
    # both log it and leave it fully intact for FastAPI's own routing/
    # pydantic body parsing (JSON, form/multipart, etc.) further down.
    try:
        request_body_bytes = await request.body()
    except Exception:  # pragma: no cover - defensive: never let logging break a request
        request_body_bytes = b""

    response = await call_next(request)

    duration_ms = (perf_counter() - start) * 1000
    route = request.scope.get("route")
    response_content_type = response.headers.get("content-type") or ""

    # A real streaming response (this module's own SSE endpoint today, and
    # any future one) never reaches EOF on its own -- draining
    # `response.body_iterator` to completion the way every other, genuinely
    # bounded response is handled below would block this middleware (and
    # the request) forever. Detect it by Content-Type and pass it straight
    # through unbuffered instead: still logged (method/path/status/
    # duration), just without a captured body, and Starlette streams it to
    # the client exactly as if this middleware were not there.
    if response_content_type.startswith("text/event-stream"):
        entry = LogEntry(
            seq=next(_seq_counter),
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=request.method,
            path=request.url.path,
            query_string=request.url.query,
            route_path=getattr(route, "path", None),
            path_params=dict(request.path_params),
            query_params=dict(request.query_params),
            request_headers=_headers_of_interest(request.headers),
            request_body_preview=_preview(request_body_bytes),
            response_status=response.status_code,
            response_body_preview="(streaming response - body not captured)",
            response_content_type=response_content_type,
            duration_ms=duration_ms,
            unmatched=route is None,
        )
        add_entry(entry)
        return response

    # Buffer the whole response body without breaking the response actually
    # sent to the client: `call_next` always hands back a response whose
    # `body_iterator` yields the complete body FastAPI/Starlette already
    # produced (true even for a plain `Response(content=...)` -- every
    # existing non-streaming endpoint in this mock uses that or
    # JSONResponse). We fully drain it, then rebuild an equivalent Response
    # carrying the exact same bytes, status code and headers (content-type/
    # content-length included) -- no observable difference to the client.
    response_body_bytes = b""
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        response_body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()

    new_response = Response(
        content=response_body_bytes,
        status_code=response.status_code,
        headers=dict(response.headers),
    )

    entry = LogEntry(
        seq=next(_seq_counter),
        timestamp=datetime.now(timezone.utc).isoformat(),
        method=request.method,
        path=request.url.path,
        query_string=request.url.query,
        route_path=getattr(route, "path", None),
        path_params=dict(request.path_params),
        query_params=dict(request.query_params),
        request_headers=_headers_of_interest(request.headers),
        request_body_preview=_preview(request_body_bytes),
        response_status=new_response.status_code,
        response_body_preview=_preview(response_body_bytes),
        response_content_type=new_response.headers.get("content-type"),
        duration_ms=duration_ms,
        unmatched=route is None,
    )
    add_entry(entry)

    return new_response
