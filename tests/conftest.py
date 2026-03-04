"""
Pytest configuration and fixtures for Research PDF File Renamer tests.

This module provides common fixtures and configuration for all tests.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="function")
def app():
    """Create and configure a Flask application for testing."""
    from backend.app import create_app
    from backend.database import db as _db

    # Create app with testing config (uses TestingConfig from backend.config)
    app = create_app("testing")

    # Set test-specific folders
    app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp()
    app.config["DOWNLOAD_FOLDER"] = tempfile.mkdtemp()

    with app.app_context():
        _db.create_all()
        yield app

        # Cleanup - within app context
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Get a database session with automatic rollback."""
    from backend.database import db as _db

    with app.app_context():
        # Create all tables
        _db.create_all()

        yield _db

        # Cleanup: remove session and drop all tables
        _db.session.expire_all()
        _db.session.close()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Create a test client for the application."""
    return app.test_client()


@pytest.fixture(scope="function")
def auth_headers(client, db):
    """Create authentication headers for a test user."""
    from backend.models import User
    import bcrypt

    # Create a test user
    password_hash = bcrypt.hashpw(b"test_password123", bcrypt.gensalt()).decode("utf-8")
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash=password_hash,
        is_approved=True,
        is_active=True,
        is_admin=False,
    )
    db.session.add(user)
    db.session.commit()

    # Login and get token
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test_password123"},
    )

    data = response.get_json()
    token = data.get("token")

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_headers(client, db):
    """Create authentication headers for an admin user."""
    from backend.models import User
    import bcrypt

    # Create an admin user
    password_hash = bcrypt.hashpw(b"admin_password123", bcrypt.gensalt()).decode(
        "utf-8"
    )
    admin = User(
        name="Admin User",
        email="admin@example.com",
        password_hash=password_hash,
        is_approved=True,
        is_active=True,
        is_admin=True,
    )
    db.session.add(admin)
    db.session.commit()

    # Login and get token
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin_password123"},
    )

    data = response.get_json()
    token = data.get("token")

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def sample_pdf():
    """Provide a sample PDF file path for testing."""
    # This should point to a real sample PDF in the fixtures directory
    pdf_path = Path(__file__).parent / "fixtures" / "sample_paper.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    return None


@pytest.fixture(scope="function")
def temp_upload_dir(app):
    """Create a temporary directory for file uploads."""
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def mock_llm_service(monkeypatch):
    """Mock the LLM service to avoid actual API calls."""

    class MockLLMService:
        def __init__(self, config):
            self.provider = "test"
            self.model = "test-model"
            self.api_key = "test-key"

        def extract_paper_metadata(self, text, user_preferences=None):
            return {
                "title": "Test Paper Title",
                "authors": ["Author One", "Author Two"],
                "year": 2024,
                "suggested_filename": "Author_One_2024_Test_Paper.pdf",
            }, None

    from backend.services import llm_service

    monkeypatch.setattr(llm_service, "LLMService", MockLLMService)
    return MockLLMService


@pytest.fixture(scope="function")
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "password": "SecurePassword123!",
        "password_confirm": "SecurePassword123!",
    }


@pytest.fixture(scope="function")
def sample_pdf_metadata():
    """Provide sample PDF metadata for testing."""
    return {
        "title": "Sample Research Paper",
        "authors": ["Jane Doe", "John Smith"],
        "year": 2024,
        "abstract": "This is a sample abstract for testing purposes.",
        "suggested_filename": "Doe_2024_Sample_Research_Paper.pdf",
    }


# Pytest hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers dynamically."""
    for item in items:
        # Add slow marker to tests that have @pytest.mark.slow
        if "slow" in item.keywords:
            item.add_marker(pytest.mark.slow)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "auth: Authentication tests")
