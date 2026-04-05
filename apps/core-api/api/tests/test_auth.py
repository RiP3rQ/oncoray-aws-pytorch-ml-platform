from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from core_api.auth import TokenValidationError, create_access_token, decode_access_token


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "user@example.com"
    assert isinstance(payload["id"], int)
    assert "created_at" in payload


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A user with this email already exists."


@pytest.mark.asyncio
async def test_login_returns_access_token(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"].count(".") == 2
    assert "expires_at" in payload
    assert payload["user"]["email"] == "user@example.com"

    claims = decode_access_token(payload["access_token"])
    assert claims.subject == payload["user"]["id"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_logout_invalidates_token(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})
    login_response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )
    access_token = login_response.json()["access_token"]

    logout_response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout_response.status_code == 204

    second_logout_response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert second_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_health_and_readiness_report_ready_dependencies(client: AsyncClient) -> None:
    liveness_response = await client.get("/livez")
    assert liveness_response.status_code == 200
    assert liveness_response.json() == {"status": "ok"}

    readiness_response = await client.get("/readyz")
    assert readiness_response.status_code == 200
    assert readiness_response.json() == {"status": "ok", "model_ready": True, "db_ready": True}

    health_response = await client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok", "model_ready": True, "db_ready": True}


@pytest.mark.asyncio
async def test_login_is_rate_limited_after_repeated_failures(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "user@example.com", "password": "supersecret"})

    for _ in range(5):
        response = await client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "wrongpass"},
        )
        assert response.status_code == 401

    limited_response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrongpass"},
    )
    assert limited_response.status_code == 429
    retry_after = int(limited_response.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_decode_access_token_rejects_expired_tokens() -> None:
    issued_at = datetime.now(UTC) - timedelta(minutes=30)
    expired_token = create_access_token(1, issued_at=issued_at)

    with pytest.raises(TokenValidationError, match="expired"):
        decode_access_token(expired_token.token, now=datetime.now(UTC))
