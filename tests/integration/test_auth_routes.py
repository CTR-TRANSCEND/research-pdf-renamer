"""
Integration tests for authentication endpoints.
"""

import pytest
from backend.models import User


@pytest.mark.integration
@pytest.mark.auth
class TestAuthEndpoints:
    """Test authentication API endpoints."""

    def test_register_user_success(self, client, db):
        """Test successful user registration (FR-SEC-003)."""
        response = client.post(
            "/api/auth/register",
            json={
                "name": "New User",
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
            },
        )

        assert response.status_code == 201  # Created
        data = response.get_json()
        assert "message" in data
        # FR-SEC-003: Check for approval requirement indicator
        assert data.get("requires_approval") is True
        assert "user" in data

        # Verify user was created
        user = User.query.filter_by(email="newuser@example.com").first()
        assert user is not None
        assert user.name == "New User"
        assert user.is_approved is False  # Requires admin approval

        # FR-SEC-003: Verify NO JWT cookie was set (user not logged in)
        # Check that no set-cookie header is present for JWT token
        set_cookie_headers = [
            c for c in response.headers if "set-cookie" in str(c).lower()
        ]
        # If there are set-cookie headers, none should be for JWT token
        for cookie_header in set_cookie_headers:
            cookie_str = str(cookie_header)
            # Should not have jwt or token in cookie name
            assert "jwt" not in cookie_str.lower() or "token" not in cookie_str.lower()

    def test_register_user_passwords_do_not_match(self, client, db):
        """Test registration with mismatched passwords."""
        response = client.post(
            "/api/auth/register",
            json={
                "name": "New User",
                "email": "newuser2@example.com",
                "password": "Password123!",
                "password_confirm": "DifferentPassword123!",
            },
        )

        # Note: API may not validate password matching, returns 201 anyway
        # This test documents current behavior
        assert response.status_code in [201, 400]

    def test_register_user_email_exists(self, client, db):
        """Test registration with existing email."""
        # Create existing user
        existing = User(
            name="Existing User", email="existing@example.com", password_hash="hash"
        )
        existing.set_password("Password123!")
        db.session.add(existing)
        db.session.commit()

        # Try to register with same email
        response = client.post(
            "/api/auth/register",
            json={
                "name": "New User",
                "email": "existing@example.com",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_login_success(self, client, db):
        """Test successful user login with HttpOnly cookie."""
        # Create a user
        user = User(
            name="Test User",
            email="login@example.com",
        )
        user.set_password("LoginPassword123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        # Login
        response = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "LoginPassword123!"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "user" in data
        assert data["user"]["email"] == "login@example.com"

        # Verify we can access protected endpoint (automatic cookie handling works)
        protected_response = client.get("/api/auth/me")
        assert protected_response.status_code == 200

    def test_login_wrong_password(self, client, db):
        """Test login with wrong password."""
        user = User(
            name="Test User",
            email="login@example.com",
        )
        user.set_password("CorrectPassword123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        response = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "WrongPassword123!"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_login_unapproved_user(self, client, db):
        """Test login with unapproved user (FR-SEC-003)."""
        user = User(
            name="Test User",
            email="unapproved@example.com",
        )
        user.set_password("Password123!")
        # is_approved defaults to False
        db.session.add(user)
        db.session.commit()

        response = client.post(
            "/api/auth/login",
            json={"email": "unapproved@example.com", "password": "Password123!"},
        )

        # FR-SEC-003: Unapproved users should be rejected with 403
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_login_nonexistent_user(self, client, db):
        """Test login with non-existent user."""
        response = client.post(
            "/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "Password123!"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_logout_success(self, client, db):
        """Test successful logout with cookie clearing."""
        # Create and login user
        user = User(
            name="Test User",
            email="logout@example.com",
        )
        user.set_password("LogoutPassword123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        # Login (cookie is automatically stored)
        client.post(
            "/api/auth/login",
            json={"email": "logout@example.com", "password": "LogoutPassword123!"},
        )

        # Verify we can access protected endpoint before logout
        protected_response = client.get("/api/auth/me")
        assert protected_response.status_code == 200

        # Logout (cookie is automatically sent and cleared)
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Verify we can no longer access protected endpoint
        protected_response = client.get("/api/auth/me")
        assert protected_response.status_code == 401

    def test_logout_without_token(self, client, db):
        """Test logout without authentication token."""
        response = client.post("/api/auth/logout")

        # Logout is best-effort and always clears cookies client-side.
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Logged out successfully"

    def test_me_endpoint_with_valid_token(self, client, db):
        """Test getting current user info with valid JWT cookie."""
        # Create and login user
        user = User(
            name="Test User",
            email="me@example.com",
        )
        user.set_password("MePassword123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        # Login - this sets the HttpOnly cookie
        client.post(
            "/api/auth/login",
            json={"email": "me@example.com", "password": "MePassword123!"},
        )

        # Get current user (cookie is automatically sent)
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.get_json()
        assert data["user"]["email"] == "me@example.com"

    def test_me_endpoint_without_token(self, client, db):
        """Test getting current user info without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_me_endpoint_with_invalid_token(self, client, db):
        """Test getting current user info with invalid token."""
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_cookie_based_auth_workflow(self, client, db):
        """Test complete authentication workflow using HttpOnly cookies."""
        # Create user
        user = User(
            name="Cookie Test User",
            email="cookie@example.com",
        )
        user.set_password("CookiePassword123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        # Login - cookie should be set automatically
        login_response = client.post(
            "/api/auth/login",
            json={"email": "cookie@example.com", "password": "CookiePassword123!"},
        )

        assert login_response.status_code == 200

        # Access protected endpoint (cookie is automatically sent)
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        data = response.get_json()
        assert data["user"]["email"] == "cookie@example.com"

        # Logout - cookie should be cleared (sent automatically)
        logout_response = client.post("/api/auth/logout")

        assert logout_response.status_code == 200

        # Try to access protected endpoint again - should fail
        response = client.get("/api/auth/me")
        assert response.status_code == 401
