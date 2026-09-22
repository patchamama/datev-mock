"""FastAPI application entrypoint for the DATEV Local API Mock.

Serves the same 3 endpoints as the real DATEV Desktop API on port 58452:
`diagnostics/v1/echo`, `master-data/v1/clients`, `accounting/v1/clients`.
Swagger UI is available at `/docs` (FastAPI default) for manual testing.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.routers import accounting, diagnostics, master_data

app = FastAPI(
    title="DATEV Local API Mock",
    description=(
        "Local mock of DATEV's Desktop API (diagnostics, master-data, "
        "accounting), reproducing the real DataContractSerializer XML shapes."
    ),
    version="0.1.0",
)

app.include_router(diagnostics.router)
app.include_router(master_data.router)
app.include_router(accounting.router)
