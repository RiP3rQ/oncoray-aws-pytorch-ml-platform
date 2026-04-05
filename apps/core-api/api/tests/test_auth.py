from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_creates_user(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "user@example.com"
    assert isinstance(payload["id"], int)
    assert "created_at" in payload


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists."


def test_login_returns_access_token(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["user"]["email"] == "user@example.com"


def test_login_rejects_invalid_password(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_logout_invalidates_token(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})
    login_response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )
    access_token = login_response.json()["access_token"]

    logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout_response.status_code == 204

    second_logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert second_logout_response.status_code == 401
