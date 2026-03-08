"""
E2E tests for admin user management workflow.

Covers REQ-E2E-003: Admin User Management
- Admin can list all users
- Admin can approve a pending user
- Admin can deactivate an active user
- Non-admin users are blocked from admin endpoints
"""

import pytest
import bcrypt
from backend.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_regular_user(db, email: str, password: str, approved: bool = False):
    """Insert a regular (non-admin) user directly into the database."""
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(
        name="Regular User",
        email=email,
        password_hash=pw_hash,
        is_approved=approved,
        is_active=True,
        is_admin=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_admin_can_list_users(admin_client, db):
    """Admin can retrieve the list of all users."""
    response = admin_client.get("/api/admin/users")
    assert response.status_code == 200
    data = response.get_json()
    # The endpoint may return a list directly or a dict with a "users" key
    assert isinstance(data, (list, dict))


@pytest.mark.e2e
def test_admin_can_approve_user(admin_client, db):
    """Admin can approve a pending user so they can log in."""
    user = _create_regular_user(db, "pending_e2e@example.com", "PendPass123!")

    # User is not yet approved
    assert user.is_approved is False

    response = admin_client.post(f"/api/admin/approve/{user.id}")
    assert response.status_code == 200

    # Verify approval in the database
    db.session.refresh(user)
    assert user.is_approved is True


@pytest.mark.e2e
def test_admin_can_deactivate_user(admin_client, db, app):
    """Admin can deactivate an active user; the user can no longer log in."""
    password = "ActivePass123!"
    user = _create_regular_user(db, "active_e2e@example.com", password, approved=True)

    # Deactivate the user
    response = admin_client.post(f"/api/admin/deactivate/{user.id}")
    assert response.status_code == 200

    # Verify in database
    db.session.refresh(user)
    assert user.is_active is False

    # The deactivated user should not be able to log in
    user_client = app.test_client()
    login_resp = user_client.post(
        "/api/auth/login",
        json={"email": "active_e2e@example.com", "password": password},
    )
    assert login_resp.status_code in (401, 403)


@pytest.mark.e2e
def test_non_admin_cannot_access_admin_endpoints(e2e_client, db, approved_user):
    """A regular authenticated user is denied access to admin endpoints."""
    # Log in as the regular approved user
    e2e_client.post(
        "/api/auth/login",
        json={
            "email": approved_user["email"],
            "password": approved_user["password"],
        },
    )

    # Try to list users via admin endpoint
    response = e2e_client.get("/api/admin/users")
    assert response.status_code in (401, 403)
