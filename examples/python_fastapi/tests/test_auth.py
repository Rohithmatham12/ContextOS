"""Tests for auth routes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_success(client: TestClient) -> None:
    resp = client.post("/users/token", data={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client: TestClient) -> None:
    resp = client.post("/users/token", data={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_me_with_token(client: TestClient) -> None:
    token_resp = client.post("/users/token", data={"username": "alice", "password": "secret"})
    token = token_resp.json()["access_token"]
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
