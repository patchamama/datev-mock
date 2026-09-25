"""Resource snapshot export (`odd/tasks/datev-mock-resource-snapshot-export.md`):
`POST /admin/api/snapshots`.

## Problem this solves

"Save every distinct request/response observed for a given resource to disk,
so it can be reloaded later" -- e.g. to capture real-looking traffic once and
replay it offline, or to seed the existing custom-overrides mechanism
(`app/overrides.py`) with real captured shapes instead of hand-crafted ones.

## Design (see the task doc for the full write-up)

A real correctness bug was avoided by reading the code first: naively
"saving from the log" would silently write **truncated** bodies for any
response over `request_log._PREVIEW_LIMIT` (~2000 chars) -- the ring buffer
only ever stores a preview, by design, for the live admin log viewer's own
purposes. The full response body is never persisted anywhere.

Instead, the request log is used only to learn *which distinct
(method, path, query_string) combinations were observed* for a resource --
those fields are never truncated. For each distinct GET combination, this
endpoint re-issues the request server-side (a same-origin, self-loopback
HTTP call back into this very same running backend, via
`request.base_url`) to obtain a fresh, complete, current response body, and
writes it to `snapshots/<mirrored-path>[__<query-hash>].<json|xml>` -- the
exact raw body format `app/overrides.py`'s upload endpoint already accepts
(content-based detection, not filename-based), so a saved snapshot is
immediately re-usable via the existing overrides UI.

## Self-loopback safety (see the task doc's own verification)

This handler is a plain `def` (sync), exactly like the already-shipped F5
relay (`app/routers/relay.py`): FastAPI runs sync handlers in Starlette's
threadpool, so the blocking `requests.get()` call below runs on its own
worker thread, not the event loop -- it cannot deadlock waiting on itself.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests
from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from app import request_log

router = APIRouter(tags=["admin"])

SNAPSHOTS_ENDPOINT = "/admin/api/snapshots"

# Repo-root `snapshots/` (mirrors the Java side's `spring-boot/snapshots/`,
# both gitignored runtime state -- see the task doc's scope). Module-level
# so tests can monkeypatch it to a throwaway directory, the same convention
# `app.config.SETTINGS_PATH` already uses (see tests/test_admin_api.py).
_SNAPSHOTS_ROOT = Path(__file__).resolve().parent.parent.parent / "snapshots"

# Fixed server-side ceiling for the self-loopback outbound call this
# endpoint makes on its own behalf -- same rationale as F5's relay ceiling
# (app/routers/relay.py), just scoped to a call this same process always
# answers itself, so a hang here would indicate this process is already
# wedged, not a slow remote target.
_SNAPSHOT_TIMEOUT_SECONDS = 30


class SnapshotRequest(BaseModel):
    path_prefix: str

    @field_validator("path_prefix")
    @classmethod
    def path_prefix_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path_prefix is required")
        return value


def _query_suffix(query_string: str) -> str:
    """Collapses a query string into a short, safe, collision-resistant
    filename suffix -- a short hash of the *sorted* query string (so the
    same params in a different order still land on the same file), empty
    when there's no query string at all."""
    if not query_string:
        return ""
    normalized = _canonical_query_string(query_string)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return f"__{digest}"


def _canonical_query_string(query_string: str) -> str:
    """Canonical query identity for deduplication and filenames.

    Preserve the first observed raw query when re-issuing the request, but
    treat parameter order as irrelevant when deciding whether it has already
    been exported. This keeps one canonical filename and an honest `saved`
    count for equivalent variants.
    """
    return "&".join(sorted(query_string.split("&"))) if query_string else ""


def _extension_for_content_type(content_type: str | None) -> str:
    """Content-type decides the extension (see the task doc's scope) --
    mirrors `app/overrides.py::detect_content_type`'s xml-before-json
    ordering in spirit, but from the re-issued response's own header rather
    than sniffing the body, since the header is already authoritative here."""
    ct = (content_type or "").lower()
    if "xml" in ct:
        return "xml"
    if "json" in ct:
        return "json"
    return "txt"


def _snapshot_file_path(root: Path, path: str, query_string: str, ext: str) -> Path:
    rel = path.lstrip("/")
    return root / f"{rel}{_query_suffix(query_string)}.{ext}"


def _distinct_get_variants(path_prefix: str) -> list[tuple[str, str]]:
    """Every canonically distinct (path, query_string) GET combination
    observed for a resource path/prefix, oldest-first. Only
    `method`/`path`/`query_string` from each log entry are read; the
    (possibly truncated) body preview is never touched."""
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for entry in request_log.get_backlog():
        if entry["method"] != "GET":
            continue
        path = entry["path"]
        if not path.startswith(path_prefix):
            continue
        query_string = entry["query_string"]
        key = (path, _canonical_query_string(query_string))
        if key in seen:
            continue
        seen.add(key)
        ordered.append((path, query_string))
    return ordered


@router.post(SNAPSHOTS_ENDPOINT)
def save_snapshots(payload: SnapshotRequest, request: Request) -> dict:
    base_url = str(request.base_url).rstrip("/")

    saved_files: list[str] = []
    for path, query_string in _distinct_get_variants(payload.path_prefix):
        target = f"{base_url}{path}"
        if query_string:
            target = f"{target}?{query_string}"

        response = requests.get(target, timeout=_SNAPSHOT_TIMEOUT_SECONDS)

        ext = _extension_for_content_type(response.headers.get("content-type"))
        file_path = _snapshot_file_path(_SNAPSHOTS_ROOT, path, query_string, ext)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(response.content)
        saved_files.append(str(file_path))

    return {"saved": len(saved_files), "files": saved_files}
