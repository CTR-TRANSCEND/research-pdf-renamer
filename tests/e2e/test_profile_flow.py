"""
E2E tests for user profile and settings workflow.

Covers REQ-E2E-004: Profile Settings and Format Builder
- Authenticated user can view their profile
- Authenticated user can update filename format settings
"""

import pytest


@pytest.mark.e2e
def test_user_can_view_profile(e2e_client, db, approved_user):
    """An approved, authenticated user can retrieve their profile."""
    e2e_client.post(
        "/api/auth/login",
        json={
            "email": approved_user["email"],
            "password": approved_user["password"],
        },
    )

    response = e2e_client.get("/api/auth/me")
    assert response.status_code == 200

    data = response.get_json()
    # Profile must include the user's email
    user_info = data.get("user") or data
    assert user_info.get("email") == approved_user["email"]


@pytest.mark.e2e
def test_user_can_update_settings(e2e_client, db, approved_user):
    """An approved, authenticated user can update their filename format settings.

    The update must persist so a subsequent GET returns the new value.
    """
    e2e_client.post(
        "/api/auth/login",
        json={
            "email": approved_user["email"],
            "password": approved_user["password"],
        },
    )

    # Update to a different built-in format (endpoint accepts POST)
    update_resp = e2e_client.post(
        "/api/auth/update-settings",
        json={"filename_format": "Author_Year_Title"},
    )
    assert update_resp.status_code == 200, (
        f"Settings update failed: {update_resp.get_json()}"
    )

    # Verify the update persisted
    settings_resp = e2e_client.get("/api/auth/settings")
    assert settings_resp.status_code == 200
    settings_data = settings_resp.get_json()
    settings = settings_data.get("settings") or settings_data
    assert settings.get("filename_format") == "Author_Year_Title"
