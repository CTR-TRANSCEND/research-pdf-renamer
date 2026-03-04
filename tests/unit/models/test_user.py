"""
Unit tests for the User model.
"""

import pytest
from backend.models import User
import bcrypt


class TestUserModel:
    """Test User model functionality."""

    def test_create_user(self, db):
        """Test creating a new user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=True,
            is_active=True,
            is_admin=False,
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_approved is True
        assert user.is_active is True
        assert user.is_admin is False

    def test_user_password_hashing(self, db):
        """Test password hashing with bcrypt."""
        user = User(
            name="Test User",
            email="test@example.com",
        )
        user.set_password("SecurePassword123!")
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)

        # Verify password hash is set
        assert user.password_hash is not None
        assert len(user.password_hash) == 60  # bcrypt hash length

        # Verify password can be checked
        assert user.check_password("SecurePassword123!") is True
        assert user.check_password("WrongPassword") is False

    def test_user_get_max_files_approved(self, db):
        """Test get_max_files for approved user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=True,
        )
        db.session.add(user)
        db.session.commit()

        assert user.get_max_files() == 30

    def test_user_get_max_files_unapproved(self, db):
        """Test get_max_files for unapproved user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=False,
        )
        db.session.add(user)
        db.session.commit()

        assert user.get_max_files() == 5

    def test_user_get_max_files_custom_limit(self, db):
        """Test get_max_files with custom limit."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=True,
            max_files_per_session=15,
        )
        db.session.add(user)
        db.session.commit()

        assert user.get_max_files() == 15

    def test_user_is_user_active_approved(self, db):
        """Test is_user_active for approved user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=True,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        assert user.is_user_active() is True

    def test_user_is_user_active_unapproved(self, db):
        """Test is_user_active for unapproved user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=False,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        assert user.is_user_active() is False

    def test_user_is_user_active_deactivated(self, db):
        """Test is_user_active for deactivated user."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
            is_approved=True,
            is_active=False,
        )
        db.session.add(user)
        db.session.commit()

        assert user.is_user_active() is False

    def test_user_email_unique(self, db):
        """Test that email addresses must be unique."""
        user1 = User(
            name="Test User 1",
            email="test@example.com",
            password_hash="dummy_hash",
        )
        user2 = User(
            name="Test User 2",
            email="test@example.com",  # Duplicate email
            password_hash="dummy_hash",
        )
        db.session.add(user1)
        db.session.commit()

        # Adding second user with same email should fail
        db.session.add(user2)
        with pytest.raises(Exception):  # IntegrityError
            db.session.commit()

    def test_user_default_values(self, db):
        """Test default values for user fields."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)

        assert user.is_approved is False  # Default
        assert user.is_admin is False  # Default
        assert user.is_active is True  # Default
        assert user.filename_format == "Author_Year_Journal_Keywords"  # Default
        assert user.auto_download is True  # Default
        assert user.max_files_per_session is None  # Default

    def test_user_repr(self, db):
        """Test User __repr__ method."""
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
        )
        db.session.add(user)
        db.session.commit()

        assert repr(user) == "<User test@example.com>"
