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
app.add_middleware(
    CORSMiddleware,
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
