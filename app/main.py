"""FastAPI application entrypoint for the DATEV Local API Mock.

Serves the same 3 endpoints as the real DATEV Desktop API on port 58452:
`diagnostics/v1/echo`, `master-data/v1/clients`, `accounting/v1/clients`.
Swagger UI is available at `/docs` (FastAPI default) for manual testing.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.routers import accounting, admin, diagnostics, dms, master_data

app = FastAPI(
    title="DATEV Local API Mock",
    description=(
        "Local mock of DATEV's Desktop API (diagnostics, master-data, "
        "accounting), reproducing the real DataContractSerializer XML shapes. "
        "Also serves a small admin/settings UI at /admin."
    ),
    version="0.1.0",
)

app.include_router(diagnostics.router)
app.include_router(master_data.router)
app.include_router(accounting.router)
app.include_router(admin.router)
app.include_router(dms.router)
