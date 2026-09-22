"""Shared pytest fixtures for the DATEV mock API test suite.

RED phase: `app.main` does not exist yet. Importing it here is intentional —
collection is expected to fail (ModuleNotFoundError) until the GREEN-phase
implementation is written. That failure is the correct RED signal for this
step; do not add try/except around this import to hide it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402  (intentionally fails until app/ exists)


@pytest.fixture()
def client() -> TestClient:
    """A FastAPI TestClient bound to the mock app, one per test."""
    return TestClient(app)
