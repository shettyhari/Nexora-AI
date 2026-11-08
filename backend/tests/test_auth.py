import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@nexora.ai",
            "username": "newuser",
            "password": "SecurePassword123!",
            "display_name": "New Nexora User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@nexora.ai",
            "username": "dupuser1",
            "password": "SecurePassword123!"
        }
    )
    # Second registration with same email
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@nexora.ai",
            "username": "dupuser2",
            "password": "SecurePassword123!"
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginuser@nexora.ai",
            "username": "loginuser",
            "password": "MySecretPassword123"
        }
    )
    # Login with email
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "login": "loginuser@nexora.ai",
            "password": "MySecretPassword123"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "login": "nonexistent@nexora.ai",
            "password": "WrongPassword!"
        }
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_protected(client, auth_headers):
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@nexora.ai"
    assert data["username"] == "testuser"
    assert data["profile"] is not None
    assert data["preferences"] is not None


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
