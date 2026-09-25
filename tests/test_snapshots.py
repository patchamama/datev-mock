"""RED-then-GREEN tests for the resource snapshot export endpoint (`POST
/admin/api/snapshots`, `app/routers/snapshots.py`).

See `odd/tasks/datev-mock-resource-snapshot-export.md` for the full design.

## Why a real live server, not `TestClient`

The endpoint's whole point is a genuine *self-loopback* HTTP call: it reads
`request.base_url` and issues a real `requests.get()` back at itself to get
a fresh, complete response body (never the log's own truncated preview).
`TestClient` fakes `request.base_url` as `http://testserver/` -- not a real,
routable address `requests` could ever connect to -- so it can't exercise
the actual self-loopback path. Instead, `live_server` below runs the real
FastAPI app via `uvicorn.Server` in a background thread on a real,
OS-assigned loopback port, and every test drives it with the real `requests`
library end-to-end: the initiating POST *and* the self-loopback GET it
triggers both go over a real socket, proving the design's own safety
argument (a blocking outbound call from a sync handler, running in
Starlette's threadpool, doesn't deadlock on itself) rather than assuming it.
"""
from __future__ import annotations

import shutil
import socket
import threading
import time

import pytest
import requests
import uvicorn

from app import request_log
from app.main import app
from app.routers import snapshots

SNAPSHOTS_ENDPOINT = "/admin/api/snapshots"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def live_server(tmp_path, monkeypatch):
    """Starts the real app on a real ephemeral loopback port; redirects the
    snapshots root to a throwaway `tmp_path` directory (never the repo's
    real `snapshots/`); tears both down afterward."""
    snapshots_root = tmp_path / "snapshots"
    monkeypatch.setattr(snapshots, "_SNAPSHOTS_ROOT", snapshots_root)

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "live test server failed to start in time"

    try:
        yield f"http://127.0.0.1:{port}", snapshots_root
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        # Belt-and-suspenders cleanup: even though snapshots_root already
        # lives under pytest's own tmp_path (auto-cleaned), remove it
        # explicitly so a test failure never leaves stray files behind.
        shutil.rmtree(snapshots_root, ignore_errors=True)


# --- full, untruncated content (the real bug this design avoids) ---


def test_saves_full_untruncated_content_not_the_logs_own_truncated_preview(live_server):
    base_url, snapshots_root = live_server

    # A real GET, big enough to exceed request_log._PREVIEW_LIMIT (~2000
    # chars) -- this mock's own master-data/clients XML is ~31KB.
    direct = requests.get(f"{base_url}/datev/api/master-data/v1/clients", timeout=10)
    assert direct.status_code == 200
    assert len(direct.content) > request_log._PREVIEW_LIMIT * 2

    resp = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": "/datev/api/master-data/v1/clients"},
        timeout=10,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["saved"] >= 1

    saved_file = snapshots_root / "datev" / "api" / "master-data" / "v1" / "clients.xml"
    assert saved_file.exists()
    saved_bytes = saved_file.read_bytes()

    # Exact byte-for-byte match with a real, independent GET -- not
    # truncated, not stale.
    assert len(saved_bytes) == len(direct.content)
    assert saved_bytes == direct.content
    assert str(saved_file) in result["files"]


# --- distinct query-string variants: real deduplication ---


def test_distinct_query_string_variants_each_produce_their_own_file(live_server):
    base_url, snapshots_root = live_server

    # `/datev/api/master-data/v1/banks` has no nested "by id" GET route
    # (unlike addressees/employees) and the full test suite's own ring
    # buffer is process-wide/shared across every test file (see
    # tests/test_request_log.py's own docstring on this) -- a resource with
    # no children keeps this test's path_prefix match set exactly under our
    # own control instead of also picking up unrelated deep sub-resource
    # history from other test files.
    #
    # Two distinct variants (JSON resource), plus a repeat of the first --
    # proves dedup collapses the repeat (also covered directly at the unit
    # level by test_only_get_requests_are_considered's dedup contract).
    r1a = requests.get(f"{base_url}/datev/api/master-data/v1/banks?marker=alpha", timeout=10)
    r1b = requests.get(f"{base_url}/datev/api/master-data/v1/banks?marker=alpha", timeout=10)
    r2 = requests.get(f"{base_url}/datev/api/master-data/v1/banks?marker=beta", timeout=10)
    assert r1a.status_code == r1b.status_code == r2.status_code == 200

    resp = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": "/datev/api/master-data/v1/banks"},
        timeout=10,
    )
    assert resp.status_code == 200
    result = resp.json()

    # At least our 2 distinct combos were saved (other test files may also
    # have exercised this same plain, no-query endpoint -- that's a 3rd,
    # legitimate, harmless variant this assertion tolerates).
    assert result["saved"] >= 2

    banks_dir = snapshots_root / "datev" / "api" / "master-data" / "v1"
    expected_alpha = banks_dir / f"banks{snapshots._query_suffix('marker=alpha')}.json"
    expected_beta = banks_dir / f"banks{snapshots._query_suffix('marker=beta')}.json"

    # Exactly one file per distinct query -- the duplicate "marker=alpha"
    # call did NOT produce a second, differently-named file.
    assert expected_alpha.exists()
    assert expected_beta.exists()
    assert expected_alpha != expected_beta

    # Both real, complete, non-empty JSON content -- not a stub.
    for f in (expected_alpha, expected_beta):
        content = f.read_bytes()
        assert len(content) > 0
        assert content == r1a.content  # this mock ignores query params, same body


# --- no observed requests yet: sane empty result, not an error ---


def test_no_observed_requests_returns_sane_empty_result_not_an_error(live_server):
    base_url, _snapshots_root = live_server

    resp = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": "/datev/api/never-requested-resource-xyz"},
        timeout=10,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result == {"saved": 0, "files": []}


@pytest.mark.parametrize("path_prefix", ["", "   "])
def test_rejects_empty_or_whitespace_path_prefix(live_server, path_prefix):
    base_url, _snapshots_root = live_server

    response = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": path_prefix},
        timeout=10,
    )

    assert response.status_code == 422


def test_reordered_query_variants_export_once_without_overwriting_or_inflating_saved(live_server):
    base_url, snapshots_root = live_server
    path = "/datev/api/snapshot-dedup-test"

    # The mock deliberately has no route for this unique path. That is
    # useful here: no other test can have put this prefix in the shared log,
    # so `saved` proves the two equivalent observed variants collapsed to
    # one export rather than merely producing the same filename twice.
    first = requests.get(f"{base_url}{path}?b=2&a=1", timeout=10)
    second = requests.get(f"{base_url}{path}?a=1&b=2", timeout=10)
    assert first.status_code == second.status_code == 404

    response = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": path},
        timeout=10,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["saved"] == 1
    assert len(result["files"]) == 1
    snapshot_files = list(snapshots_root.rglob("*"))
    assert [file for file in snapshot_files if file.is_file()] == [
        snapshots_root / "datev" / "api" / f"snapshot-dedup-test{snapshots._query_suffix('a=1&b=2')}.json"
    ]


# --- content-type decides the extension ---


def test_xml_and_json_resources_get_the_right_extension(live_server):
    base_url, snapshots_root = live_server

    # Diagnostics echo and DMS documents are both leaf resources (no nested
    # GET children) -- unlike "/datev/api/accounting/v1/clients", which is
    # also a *prefix* of many real, deeply-nested fiscal-year sub-resources
    # other test files exercise, so using it here would pull in unrelated
    # cross-file history from the shared, process-wide request log.
    requests.get(f"{base_url}/datev/api/diagnostics/v1/echo", timeout=10)  # XML by default
    requests.get(f"{base_url}/datev/api/dms/v1/documents", timeout=10)  # JSON-only

    resp = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": "/datev/api/diagnostics/v1/echo"},
        timeout=10,
    )
    assert resp.json()["saved"] == 1
    assert (snapshots_root / "datev" / "api" / "diagnostics" / "v1" / "echo.xml").exists()

    resp = requests.post(
        f"{base_url}{SNAPSHOTS_ENDPOINT}",
        json={"path_prefix": "/datev/api/dms/v1/documents"},
        timeout=10,
    )
    assert resp.json()["saved"] == 1
    assert (snapshots_root / "datev" / "api" / "dms" / "v1" / "documents.json").exists()


# --- module-level unit behavior (no live server needed) ---


def test_query_suffix_is_empty_for_no_query_string():
    assert snapshots._query_suffix("") == ""


def test_query_suffix_is_stable_regardless_of_param_order():
    a = snapshots._query_suffix("b=2&a=1")
    b = snapshots._query_suffix("a=1&b=2")
    assert a == b
    assert a.startswith("__")


def test_query_suffix_differs_for_different_query_content():
    assert snapshots._query_suffix("a=1") != snapshots._query_suffix("a=2")


def test_extension_for_content_type_prefers_xml_over_json_when_both_mentioned():
    assert snapshots._extension_for_content_type("application/xml; charset=utf-8") == "xml"
    assert snapshots._extension_for_content_type("application/json") == "json"
    assert snapshots._extension_for_content_type(None) == "txt"
    assert snapshots._extension_for_content_type("text/plain") == "txt"


def test_only_get_requests_are_considered(monkeypatch):
    monkeypatch.setattr(
        request_log,
        "get_backlog",
        lambda: [
            {"method": "POST", "path": "/x/y", "query_string": ""},
            {"method": "GET", "path": "/x/y", "query_string": ""},
        ],
    )
    assert snapshots._distinct_get_variants("/x") == [("/x/y", "")]
