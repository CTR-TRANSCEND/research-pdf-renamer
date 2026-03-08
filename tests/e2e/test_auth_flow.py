"""
E2E tests for the authentication workflow.

Covers REQ-E2E-001: User Registration Flow
- Full registration -> approval -> login -> logout lifecycle
- Registration leaves user in pending (unapproved) state
- Wrong-password login is rejected
- Logout invalidates the session cookie
"""

import pytest
from backend.models import User


@pytest.mark.e2e
def test_full_registration_login_logout_flow(e2e_client, db, admin_client):
    """User can register, be approved by admin, log in, and log out."""
    # --- STEP 1: Register ---
    register_resp = e2e_client.post(
        "/api/auth/register",
        json={
            "name": "Flow User",
            "email": "flow_user@example.com",
            "password": "FlowPass123!",
            "password_confirm": "FlowPass123!",
        },
    )
    assert register_resp.status_code == 201
    data = register_resp.get_json()
    assert data.get("requires_approval") is True

    # --- STEP 2: Admin approves the new user ---
    user = User.query.filter_by(email="flow_user@example.com").first()
    assert user is not None
    approve_resp = admin_client.post(f"/api/admin/approve/{user.id}")
    assert approve_resp.status_code == 200

    # --- STEP 3: User logs in with approved account ---
    login_resp = e2e_client.post(
        "/api/auth/login",
        json={"email": "flow_user@example.com", "password": "FlowPass123!"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()
    assert "token" in login_data or login_resp.headers.get("Set-Cookie")

    # --- STEP 4: Authenticated request succeeds ---
    profile_resp = e2e_client.get("/api/auth/me")
    assert profile_resp.status_code == 200

    # --- STEP 5: Logout ---
    logout_resp = e2e_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # --- STEP 6: Profile access is denied after logout ---
    after_logout_resp = e2e_client.get("/api/auth/me")
    assert after_logout_resp.status_code == 401


@pytest.mark.e2e
def test_registration_requires_approval_before_login(e2e_client, db):
    """Newly registered user cannot log in until an admin approves the account."""
    # Register
    reg_resp = e2e_client.post(
        "/api/auth/register",
        json={
            "name": "Pending User",
            "email": "pending_approval@example.com",
            "password": "PendingPass123!",
            "password_confirm": "PendingPass123!",
        },
    )
    assert reg_resp.status_code == 201

    # Attempt to log in without approval
    login_resp = e2e_client.post(
        "/api/auth/login",
        json={
            "email": "pending_approval@example.com",
            "password": "PendingPass123!",
        },
    )
    # Should be rejected because account is not yet approved
    assert login_resp.status_code in (401, 403)


@pytest.mark.e2e
def test_login_with_wrong_password_fails(e2e_client, db, approved_user):
    """Login attempt with an incorrect password is rejected with 401."""
    login_resp = e2e_client.post(
        "/api/auth/login",
        json={
            "email": approved_user["email"],
            "password": "WrongPassword999!",
        },
    )
    assert login_resp.status_code == 401


@pytest.mark.e2e
def test_logout_clears_session(e2e_client, db, approved_user):
    """Logging out removes the session so subsequent requests are unauthorised."""
    # Log in first
    login_resp = e2e_client.post(
        "/api/auth/login",
        json={
            "email": approved_user["email"],
            "password": approved_user["password"],
        },
    )
    assert login_resp.status_code == 200

    # Confirm access works
    profile_resp = e2e_client.get("/api/auth/me")
    assert profile_resp.status_code == 200

    # Logout
    logout_resp = e2e_client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # Access must now be forbidden
    denied_resp = e2e_client.get("/api/auth/me")
    assert denied_resp.status_code == 401
