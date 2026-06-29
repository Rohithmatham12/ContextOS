"""Tests for user registration and item CRUD."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _auth_header(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/users/token", data={"username": username, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_new_user(client: TestClient) -> None:
    resp = client.post(
        "/users/register",
        json={"username": "bob", "email": "bob@example.com", "password": "pass123"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "bob"


def test_register_duplicate_fails(client: TestClient) -> None:
    client.post(
        "/users/register",
        json={"username": "charlie", "email": "charlie@example.com", "password": "pass"},
    )
    resp = client.post(
        "/users/register",
        json={"username": "charlie", "email": "charlie@example.com", "password": "pass"},
    )
    assert resp.status_code == 400


def test_create_and_list_items(client: TestClient) -> None:
    headers = _auth_header(client, "alice", "secret")
    client.post("/items/", json={"title": "my item"}, headers=headers)
    resp = client.get("/items/", headers=headers)
    assert resp.status_code == 200
    titles = [i["title"] for i in resp.json()]
    assert "my item" in titles


def test_health_check(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
