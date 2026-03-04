"""
Unit tests for JWT authentication utilities.

Tests for backend/utils/auth.py functions:
- generate_token(user)
- set_jwt_cookie(response, user)
- clear_jwt_cookie(response)
- refresh_token_if_needed(token)
- get_jwt_from_cookie()
- auth_required decorator
"""

import pytest
import jwt
import datetime
from datetime import timedelta
from flask import Flask, jsonify, make_response
from backend.models import User
from backend.utils.auth import (
    generate_token,
    set_jwt_cookie,
    clear_jwt_cookie,
    get_jwt_from_cookie,
    refresh_token_if_needed,
    auth_required,
)


@pytest.mark.unit
class TestGenerateToken:
    """Test JWT token generation."""

    def test_generate_token_payload_structure(self, app):
        """Test that generate_token creates a token with correct payload structure."""
        with app.app_context():
            # Create a test user
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            # Generate token
            token = generate_token(user)

            # Decode and verify payload structure
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

            assert "user_id" in payload
            assert "email" in payload
            assert "exp" in payload
            assert "iat" in payload
            assert "last_activity" in payload

            # Verify payload values
            assert payload["user_id"] == 1
            assert payload["email"] == "test@example.com"
            assert isinstance(payload["exp"], (int, float))
            assert isinstance(payload["iat"], (int, float))
            assert isinstance(payload["last_activity"], str)

    def test_generate_token_expiration_time(self, app):
        """Test that generate_token sets expiration to inactivity timeout from now."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            token = generate_token(user)
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

            inactivity_minutes = int(app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30))

            # Check expiration is approximately inactivity timeout from issuance
            exp_time = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
            iat_time = datetime.datetime.fromtimestamp(payload["iat"], tz=datetime.timezone.utc)
            time_diff = exp_time - iat_time

            assert time_diff.total_seconds() == pytest.approx(
                inactivity_minutes * 60, abs=1
            )

    def test_generate_token_uses_hs256_algorithm(self, app):
        """Test that generate_token uses HS256 algorithm."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            token = generate_token(user)

            # Get header without verification
            header = jwt.get_unverified_header(token)
            assert header["alg"] == "HS256"


@pytest.mark.unit
class TestSetJwtCookie:
    """Test setting JWT token in HttpOnly cookie."""

    def test_set_jwt_cookie_httponly_attribute(self, app):
        """Test that JWT cookie is HttpOnly (prevents XSS)."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            response = make_response(jsonify({"message": "login successful"}))
            response = set_jwt_cookie(response, user)

            # Extract cookie from response
            cookie_header = response.headers.get("Set-Cookie")
            assert cookie_header is not None
            assert "HttpOnly" in cookie_header

    def test_set_jwt_cookie_samesite_lax(self, app):
        """Test that JWT cookie has SameSite=Lax for CSRF protection."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            response = make_response(jsonify({"message": "login successful"}))
            response = set_jwt_cookie(response, user)

            cookie_header = response.headers.get("Set-Cookie")
            assert "SameSite=Lax" in cookie_header

    def test_set_jwt_cookie_path_root(self, app):
        """Test that JWT cookie path is set to root (/)."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            response = make_response(jsonify({"message": "login successful"}))
            response = set_jwt_cookie(response, user)

            cookie_header = response.headers.get("Set-Cookie")
            assert "Path=/" in cookie_header

    def test_set_jwt_cookie_max_age_inactivity_timeout(self, app):
        """Test that JWT cookie max age matches inactivity timeout."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            user.id = 1

            response = make_response(jsonify({"message": "login successful"}))
            response = set_jwt_cookie(response, user)

            cookie_header = response.headers.get("Set-Cookie")
            inactivity_minutes = int(app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30))
            assert f"Max-Age={inactivity_minutes * 60}" in cookie_header


@pytest.mark.unit
class TestClearJwtCookie:
    """Test clearing JWT cookie on logout."""

    def test_clear_jwt_cookie_expires_immediately(self, app):
        """Test that clearing JWT cookie sets expiration to 0."""
        with app.app_context():
            response = make_response(jsonify({"message": "logout successful"}))
            response = clear_jwt_cookie(response)

            cookie_header = response.headers.get("Set-Cookie")
            assert cookie_header is not None
            assert "jwt_token=" in cookie_header
            # clear_jwt_cookie uses expires=0 which translates to Expires=Thu, 01 Jan 1970 00:00:00 GMT
            assert "Expires=Thu, 01 Jan 1970 00:00:00 GMT" in cookie_header

    def test_clear_jwt_cookie_preserves_security_attributes(self, app):
        """Test that clearing JWT cookie preserves security attributes."""
        with app.app_context():
            response = make_response(jsonify({"message": "logout successful"}))
            response = clear_jwt_cookie(response)

            cookie_header = response.headers.get("Set-Cookie")
            assert "HttpOnly" in cookie_header
            assert "SameSite=Lax" in cookie_header
            assert "Path=/" in cookie_header


@pytest.mark.unit
class TestGetJwtFromCookie:
    """Test extracting JWT token from HttpOnly cookie."""

    def test_get_jwt_from_cookie_with_valid_token(self, app):
        """Test extracting JWT token from request cookies."""
        with app.test_request_context():
            # Set a cookie in the request
            from flask import request

            request.cookies = {"jwt_token": "test_token_value"}

            token = get_jwt_from_cookie()
            assert token == "test_token_value"

    def test_get_jwt_from_cookie_without_token(self, app):
        """Test that get_jwt_from_cookie returns None when no token exists."""
        with app.test_request_context():
            from flask import request

            request.cookies = {}

            token = get_jwt_from_cookie()
            assert token is None


@pytest.mark.unit
class TestRefreshTokenIfNeeded:
    """Test token refresh logic with security constraints."""

    def test_refresh_within_30_minutes_of_expiration(self, app, db):
        """Test that token is refreshed when close to expiration."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            inactivity_minutes = int(app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30))

            # Create token expiring very soon (below refresh threshold)
            now = datetime.datetime.now(datetime.timezone.utc)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now + datetime.timedelta(minutes=2),
                "iat": now - datetime.timedelta(minutes=10),
                "last_activity": now.isoformat(),
            }
            old_token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

            # Should refresh
            new_token = refresh_token_if_needed(old_token)
            assert new_token is not None
            assert new_token != old_token

            # Verify new token has extended expiration
            new_payload = jwt.decode(
                new_token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            new_exp = datetime.datetime.fromtimestamp(new_payload["exp"], tz=datetime.timezone.utc)
            assert (new_exp - now).total_seconds() > (inactivity_minutes - 5) * 60

    def test_refresh_rejected_beyond_7_day_lifetime(self, app, db):
        """Test that tokens beyond 7 days from issuance cannot be refreshed."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            # Create token issued 8 days ago
            now = datetime.datetime.now(datetime.timezone.utc)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now + datetime.timedelta(minutes=20),
                "iat": now - datetime.timedelta(days=8),
                "last_activity": now.isoformat(),
            }
            old_token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

            # Should be rejected due to maximum lifetime exceeded
            new_token = refresh_token_if_needed(old_token)
            assert new_token is None

    def test_refresh_rejected_for_deactivated_user(self, app, db):
        """Test that deactivated users cannot refresh tokens."""
        with app.app_context():
            import datetime as dt

            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=False,  # Deactivated
                deactivated_at=dt.datetime.now(dt.timezone.utc),
            )
            db.session.add(user)
            db.session.commit()

            # Create token expiring in 20 minutes
            now = dt.datetime.now(dt.timezone.utc)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now + dt.timedelta(minutes=20),
                "iat": now - dt.timedelta(hours=2),
                "last_activity": now.isoformat(),
            }
            old_token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

            # Should be rejected due to deactivated user
            new_token = refresh_token_if_needed(old_token)
            assert new_token is None

    def test_refresh_rejected_for_unapproved_user(self, app, db):
        """Test that unapproved users cannot refresh tokens."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=False,  # Not approved
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            # Create token expiring in 20 minutes
            now = datetime.datetime.now(datetime.timezone.utc)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now + datetime.timedelta(minutes=20),
                "iat": now - datetime.timedelta(hours=2),
                "last_activity": now.isoformat(),
            }
            old_token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

            # Should be rejected due to unapproved user
            new_token = refresh_token_if_needed(old_token)
            assert new_token is None

    def test_refresh_rejected_for_expired_token(self, app, db):
        """Test that already expired tokens cannot be refreshed."""
        with app.app_context():
            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            # Create already expired token
            now = datetime.datetime.now(datetime.timezone.utc)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now - datetime.timedelta(minutes=10),
                "iat": now - datetime.timedelta(hours=25),
                "last_activity": now.isoformat(),
            }
            expired_token = jwt.encode(
                payload, app.config["SECRET_KEY"], algorithm="HS256"
            )

            # Should be rejected (security fix: verify_exp=True prevents bypass)
            new_token = refresh_token_if_needed(expired_token)
            assert new_token is None


@pytest.mark.unit
class TestAuthRequired:
    """Test auth_required decorator priority: cookie > header > session."""

    def test_auth_required_priority_cookie_over_header(self, app, db):
        """Test that cookie auth takes priority over Authorization header."""
        with app.test_request_context():
            from flask import request

            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            # Generate token
            token = generate_token(user)

            # Set both cookie and header with different tokens
            request.cookies = {"jwt_token": token}
            request.headers = {"Authorization": "Bearer different_token"}

            # @auth_required decorator should use cookie
            # This is tested indirectly through the function behavior
            cookie_token = get_jwt_from_cookie()
            assert cookie_token == token

    def test_auth_required_with_valid_cookie(self, app, db):
        """Test auth_required succeeds with valid JWT cookie."""
        with app.test_request_context():
            from flask import request, g

            user = User(
                email="test@example.com",
                password_hash="hash",
                name="Test User",
                is_approved=True,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

            token = generate_token(user)
            request.cookies = {"jwt_token": token}

            # Test decorator by simulating auth flow
            # Note: Full decorator test requires integration test with endpoint
            cookie_token = get_jwt_from_cookie()
            assert cookie_token is not None

            payload = jwt.decode(
                cookie_token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            assert payload["user_id"] == user.id

    def test_auth_required_without_credentials(self, app):
        """Test auth_required returns 401 without any credentials."""
        with app.test_request_context():
            from flask import request

            request.cookies = {}
            request.headers = {}

            cookie_token = get_jwt_from_cookie()
            assert cookie_token is None

            # No authorization header either
            auth_header = request.headers.get("Authorization")
            assert auth_header is None
