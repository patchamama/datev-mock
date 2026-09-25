"""FastAPI application entrypoint for the DATEV Local API Mock.

Serves the same 3 endpoints as the real DATEV Desktop API on port 58452:
`diagnostics/v1/echo`, `master-data/v1/clients`, `accounting/v1/clients`.
Swagger UI is available at `/docs` (FastAPI default) for manual testing.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db, request_log, windows_proactor_noise
from app.routers import accounting, admin, diagnostics, dms, master_data, relay


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    if sys.platform == "win32":
        windows_proactor_noise.install()
    yield


app = FastAPI(
    title="DATEV Local API Mock",
    description=(
        "Local mock of DATEV's Desktop API (diagnostics, master-data, "
        "accounting), reproducing the real DataContractSerializer XML shapes. "
        "Also serves a small admin/settings UI at /admin."
    ),
    version="0.1.0",
    lifespan=_lifespan,
)

# Lets the /admin page (SB9's configurable "API base URL") call this API
# from a different origin -- e.g. the Spring Boot mock's own /admin page
# pointed here, or vice versa. Local-only dev tool, not internet-facing, so
# a permissive localhost/127.0.0.1-any-port allow-list is appropriate.
#
# F6 (odd/tasks/datev-mock-standalone-frontend.md): also allow the literal
# "null" origin. A browser sending a request from a `file://`-opened page
# (e.g. frontend/admin.html double-clicked, or opened by
# start_java_datev_mock.bat/.sh's own post-launch browser-open) sets
# `Origin: null` on its fetch() calls -- there is no way to express that as
# part of the regex above (it isn't a URL), and Starlette's CORSMiddleware
# only ORs allow_origin_regex with a separate allow_origins list (verified by
# reading CORSMiddleware.is_allowed_origin() in
# .venv/Lib/site-packages/starlette/middleware/cors.py: it returns True if
# allow_all_origins, OR allow_origin_regex.fullmatch(origin), OR
# `origin in allow_origins` -- allow_origins and allow_origin_regex are both
# consulted, not mutually exclusive), so allow_origins=["null"] is added
# alongside the existing regex rather than trying to fold "null" into it.
# Accepted, deliberate local-dev-tool tradeoff, not an oversight: any
# `file://` page on this machine could in principle call this API, but this
# is a local mock a developer runs against their own machine, not a hosted
# multi-tenant service -- the same "real risk, explicitly called out, not
# over-engineered" pattern already used for F5's relay SSRF note.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_log.log_requests_middleware)

app.include_router(diagnostics.router)
app.include_router(master_data.router)
app.include_router(accounting.router)
app.include_router(dms.router)

# DATEV_MOCK_NON_WEB=1 (start.sh/start.bat --non-web): serve only the
# DATEV REST API, no /admin UI -- not the default, since the admin UI is
# genuinely useful for local dev/testing (settings, live request log,
# editable datasets, custom overrides).
if os.environ.get("DATEV_MOCK_NON_WEB") != "1":
    app.include_router(admin.router)
    # F5: local relay for NTLM/no-CORS real-DATEV targets (see
    # app/routers/relay.py's own docstring). Gated the same as the rest of
    # the admin API since it's only useful alongside the admin frontend.
    app.include_router(relay.router)
