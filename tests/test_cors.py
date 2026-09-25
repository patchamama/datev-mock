"""CORS behavior tests for app.main's CORSMiddleware configuration.

F6 (odd/tasks/datev-mock-standalone-frontend.md): proves the literal "null"
origin -- sent by a browser's fetch() from a file://-opened page (e.g.
frontend/admin.html opened directly, or opened by
start_java_datev_mock.bat/.sh's own post-launch browser-open) -- now gets a
matching Access-Control-Allow-Origin response header, alongside the
pre-existing localhost/127.0.0.1 regex-based allow-list (which must keep
working unchanged).
"""
from __future__ import annotations


def test_null_origin_gets_a_matching_cors_header(client):
    response = client.get("/admin/api/settings", headers={"Origin": "null"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "null"


def test_localhost_origin_still_allowed_alongside_null(client):
    response = client.get(
        "/admin/api/settings", headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unrelated_origin_still_rejected(client):
    response = client.get(
        "/admin/api/settings", headers={"Origin": "https://evil.example.com"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
