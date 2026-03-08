"""
E2E-specific fixtures for end-to-end workflow tests.

These fixtures use Flask's test client to simulate full user workflows
end-to-end without requiring a live browser or Playwright installation.
"""

import io
import os
import pytest
import bcrypt

# Minimal valid PDF content reused across E2E tests
MINIMAL_PDF_CONTENT = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Count 1
/Kids [3 0 R]
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
50 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000125 00000 n
0000000264 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
357
%%EOF"""


@pytest.fixture(scope="function")
def e2e_client(app):
    """Provide a Flask test client for E2E workflow tests."""
    return app.test_client()


@pytest.fixture(scope="function")
def registered_user(e2e_client, db):
    """Register a new user via the API and return user data.

    The user is created but NOT yet approved by admin.
    """
    user_data = {
        "name": "E2E Test User",
        "email": "e2e_user@example.com",
        "password": "E2ePassword123!",
        "password_confirm": "E2ePassword123!",
    }
    response = e2e_client.post("/api/auth/register", json=user_data)
    assert response.status_code == 201, (
        f"Registration failed: {response.get_json()}"
    )
    return {
        "email": user_data["email"],
        "password": user_data["password"],
        "name": user_data["name"],
    }


@pytest.fixture(scope="function")
def approved_user(registered_user, db, admin_client):
    """Register a user and have admin approve them.

    Returns the user credentials dict with email and password.
    """
    from backend.models import User

    user = User.query.filter_by(email=registered_user["email"]).first()
    assert user is not None

    # Admin approves the user
    response = admin_client.post(f"/api/admin/approve/{user.id}")
    assert response.status_code == 200, (
        f"Admin approval failed: {response.get_json()}"
    )

    return registered_user


@pytest.fixture(scope="function")
def admin_client(app, db):
    """Provide a Flask test client already authenticated as admin.

    Creates an admin user directly in the database and logs in via API.
    Returns the authenticated test client (JWT stored as cookie).
    """
    from backend.models import User

    password = "AdminE2ePassword123!"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    admin = User(
        name="E2E Admin",
        email="e2e_admin@example.com",
        password_hash=password_hash,
        is_approved=True,
        is_active=True,
        is_admin=True,
    )
    db.session.add(admin)
    db.session.commit()

    client = app.test_client()
    response = client.post(
        "/api/auth/login",
        json={"email": "e2e_admin@example.com", "password": password},
    )
    assert response.status_code == 200, (
        f"Admin login failed: {response.get_json()}"
    )
    return client


@pytest.fixture(scope="function")
def sample_pdf_file():
    """Return a BytesIO object containing a minimal valid PDF for upload testing."""
    return io.BytesIO(MINIMAL_PDF_CONTENT)
