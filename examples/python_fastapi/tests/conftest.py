"""Shared fixtures for FastAPI example tests."""

from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
