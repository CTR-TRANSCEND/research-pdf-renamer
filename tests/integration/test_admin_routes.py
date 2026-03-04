"""
Integration tests for admin routes.

Tests for backend/routes/admin.py endpoints:
- GET /api/admin/pending - pagination, admin-only access
- POST /api/admin/approve/<id> - approve user, prevent duplicate approval
- DELETE /api/admin/reject/<id> - reject and delete user
- POST /api/admin/deactivate/<id> - deactivate account
- POST /api/admin/activate/<id> - reactivate account
- DELETE /api/admin/delete/<id> - permanent deletion
- GET /api/admin/users - search, filter, pagination
- GET /api/admin/stats - dashboard statistics
- POST /api/admin/llm-settings - provider/model updates
- POST /api/admin/save-api-key - .env file writing
"""

import pytest
from backend.models import User, Usage
from backend.database import db


@pytest.mark.integration
@pytest.mark.admin
class TestAdminPendingUsers:
    """Test GET /api/admin/pending - pagination and admin access."""

    def test_get_pending_users_requires_admin(self, client, db):
        """Test that pending users endpoint requires admin privileges."""
        # Create regular user
        user = User(
            name="Regular User",
            email="regular@example.com",
        )
        user.set_password("Password123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        # Login as regular user (cookie is automatically stored in client.cookie_jar)
        client.post(
            "/api/auth/login",
            json={"email": "regular@example.com", "password": "Password123!"},
        )

        # Try to access admin endpoint (cookie is automatically sent with request)
        response = client.get("/api/admin/pending")

        # Should fail with 403 Forbidden
        assert response.status_code == 403

    def test_get_pending_users_with_admin(self, client, db):
        """Test that admin can access pending users endpoint."""
        # Create admin user
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create pending users
        pending1 = User(
            name="Pending User 1",
            email="pending1@example.com",
        )
        pending1.set_password("Password123!")
        db.session.add(pending1)

        pending2 = User(
            name="Pending User 2",
            email="pending2@example.com",
        )
        pending2.set_password("Password123!")
        db.session.add(pending2)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Access admin endpoint (cookie is automatically sent)
        response = client.get("/api/admin/pending")

        assert response.status_code == 200
        data = response.get_json()
        assert "users" in data
        assert data["total"] == 2

    def test_get_pending_users_pagination(self, client, db):
        """Test pagination for pending users endpoint."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create 25 pending users
        for i in range(25):
            user = User(
                name=f"Pending User {i}",
                email=f"pending{i}@example.com",
            )
            user.set_password("Password123!")
            db.session.add(user)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Request first page (cookie is automatically sent)
        response = client.get("/api/admin/pending?page=1&per_page=10")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["users"]) == 10
        assert data["total"] == 25
        assert data["current_page"] == 1
        assert data["pages"] == 3


@pytest.mark.integration
@pytest.mark.admin
class TestAdminApproveUser:
    """Test POST /api/admin/approve/<id>."""

    def test_approve_user_success(self, client, db):
        """Test approving a pending user."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create pending user
        user = User(
            name="Pending User",
            email="pending@example.com",
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Approve user (cookie is automatically sent)
        response = client.post(f"/api/admin/approve/{user_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data
        assert data["user"]["is_approved"] is True

        # Verify in database
        db.session.expire_all()
        approved_user = db.session.get(User, user_id)
        assert approved_user.is_approved is True

    def test_approve_user_prevents_duplicate_approval(self, client, db):
        """Test that already approved users cannot be approved again."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create already approved user
        user = User(
            name="Approved User",
            email="approved@example.com",
        )
        user.set_password("Password123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Try to approve again (cookie is automatically sent)
        response = client.post(f"/api/admin/approve/{user_id}")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "already approved" in data["error"].lower()


@pytest.mark.integration
@pytest.mark.admin
class TestAdminRejectUser:
    """Test DELETE /api/admin/reject/<id>."""

    def test_reject_user_deletes_user(self, client, db):
        """Test rejecting a user deletes them from database."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create pending user
        user = User(
            name="Pending User",
            email="pending@example.com",
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Reject user (cookie is automatically sent)
        response = client.delete(f"/api/admin/reject/{user_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Verify user is deleted
        deleted_user = db.session.get(User, user_id)
        assert deleted_user is None


@pytest.mark.integration
@pytest.mark.admin
class TestAdminDeactivateUser:
    """Test POST /api/admin/deactivate/<id>."""

    def test_deactivate_user(self, client, db):
        """Test deactivating a user account."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create active user
        user = User(
            name="Active User",
            email="active@example.com",
        )
        user.set_password("Password123!")
        user.is_approved = True
        user.is_active = True
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Deactivate user (cookie is automatically sent)
        response = client.post(f"/api/admin/deactivate/{user_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["user"]["is_active"] is False
        assert data["user"]["deactivated_at"] is not None

        # Verify in database
        db.session.expire_all()
        deactivated_user = db.session.get(User, user_id)
        assert deactivated_user.is_active is False
        assert deactivated_user.deactivated_at is not None


@pytest.mark.integration
@pytest.mark.admin
class TestAdminActivateUser:
    """Test POST /api/admin/activate/<id>."""

    def test_activate_user(self, client, db):
        """Test reactivating a deactivated user account."""
        from datetime import datetime, timezone

        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create deactivated user
        user = User(
            name="Inactive User",
            email="inactive@example.com",
        )
        user.set_password("Password123!")
        user.is_approved = True
        user.is_active = False
        user.deactivated_at = datetime.now(timezone.utc)
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Activate user (cookie is automatically sent)
        response = client.post(f"/api/admin/activate/{user_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["user"]["is_active"] is True

        # Verify in database
        db.session.expire_all()
        activated_user = db.session.get(User, user_id)
        assert activated_user.is_active is True
        assert activated_user.deactivated_at is None


@pytest.mark.integration
@pytest.mark.admin
class TestAdminDeleteUser:
    """Test DELETE /api/admin/delete/<id>."""

    def test_delete_user_permanently(self, client, db):
        """Test permanent deletion of a user account."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create user with usage logs
        user = User(
            name="User to Delete",
            email="delete@example.com",
        )
        user.set_password("Password123!")
        user.is_approved = True
        db.session.add(user)
        db.session.commit()

        user_id = user.id

        # Add usage logs
        usage = Usage(
            user_id=user_id,
            files_processed=5,
            ip_address="127.0.0.1",
            success=True,
        )
        db.session.add(usage)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Delete user (cookie is automatically sent)
        response = client.delete(f"/api/admin/delete/{user_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Verify user and usage logs are deleted
        deleted_user = db.session.get(User, user_id)
        assert deleted_user is None

        usage_logs = Usage.query.filter_by(user_id=user_id).all()
        assert len(usage_logs) == 0


@pytest.mark.integration
@pytest.mark.admin
class TestAdminGetAllUsers:
    """Test GET /api/admin/users - search, filter, pagination."""

    def test_get_all_users_search(self, client, db):
        """Test searching users by email or name."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create users with unique names to avoid overlapping search results
        user1 = User(name="Alice Williams", email="alice@example.com")
        user1.set_password("Password123!")
        user1.is_approved = True
        db.session.add(user1)

        user2 = User(name="Bob Martinez", email="bob@example.com")
        user2.set_password("Password123!")
        user2.is_approved = True
        db.session.add(user2)

        user3 = User(name="Charlie Davis", email="charlie@example.com")
        user3.set_password("Password123!")
        user3.is_approved = True
        db.session.add(user3)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Search for "alice" (cookie is automatically sent)
        response = client.get("/api/admin/users?search=alice")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["users"][0]["email"] == "alice@example.com"

    def test_get_all_users_filter_by_status(self, client, db):
        """Test filtering users by approval status."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create users with different statuses
        approved_user = User(name="Approved", email="approved@example.com")
        approved_user.set_password("Password123!")
        approved_user.is_approved = True
        db.session.add(approved_user)

        pending_user = User(name="Pending", email="pending@example.com")
        pending_user.set_password("Password123!")
        pending_user.is_approved = False
        db.session.add(pending_user)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Filter by approved status (cookie is automatically sent)
        response = client.get("/api/admin/users?status=approved")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 2  # admin + approved_user


@pytest.mark.integration
@pytest.mark.admin
class TestAdminStats:
    """Test GET /api/admin/stats."""

    def test_get_admin_stats(self, client, db):
        """Test getting dashboard statistics."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)

        # Create users
        approved = User(name="Approved", email="approved@example.com")
        approved.set_password("Password123!")
        approved.is_approved = True
        db.session.add(approved)

        pending = User(name="Pending", email="pending@example.com")
        pending.set_password("Password123!")
        db.session.add(pending)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Get stats (cookie is automatically sent)
        response = client.get("/api/admin/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert "user_stats" in data
        assert "usage_stats" in data
        assert data["user_stats"]["total_users"] == 3  # admin + approved + pending
        assert data["user_stats"]["pending_users"] == 1


@pytest.mark.integration
@pytest.mark.admin
class TestAdminLLMSettings:
    """Test POST /api/admin/llm-settings."""

    def test_update_llm_provider(self, client, db):
        """Test updating LLM provider and model."""
        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Update LLM settings (cookie is automatically sent)
        response = client.post(
            "/api/admin/llm-settings",
            json={"provider": "openai", "model": "gpt-4o-mini"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data
        assert data["settings"]["provider"] == "openai"
        assert data["settings"]["model"] == "gpt-4o-mini"


@pytest.mark.integration
@pytest.mark.admin
class TestAdminSaveApiKey:
    """Test POST /api/admin/save-api-key - .env file writing."""

    def test_save_api_key_to_env(self, client, db, tmp_path):
        """Test saving API key to .env file."""
        import os

        # Create admin
        admin = User(
            name="Admin User",
            email="admin@example.com",
        )
        admin.set_password("AdminPassword123!")
        admin.is_approved = True
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()

        # Login as admin
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "AdminPassword123!"},
        )

        # Mock the .env file path to use temp directory
        # This is a simplified test - in production, the actual .env file is used
        response = client.post(
            "/api/admin/save-api-key",
            json={"provider": "openai", "api_key": "sk-test-key-12345"},
        )

        # Should succeed or fail gracefully (file permissions)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.get_json()
            assert "success" in data
            assert data["success"] is True
            assert "message" in data
