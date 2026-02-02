from flask import Blueprint, request, jsonify, make_response, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from backend.models import User
from backend.database import db
from backend.utils import validate_email, validate_password, validate_name
from backend.utils.auth import (
    refresh_token_if_needed,
    auth_required,
    set_jwt_cookie,
    clear_jwt_cookie,
)
from datetime import datetime
from flask_wtf.csrf import CSRFError


def csrf_exempt():
    """Decorator to exempt a view from CSRF protection."""
    def wrapper(f):
        f.csrf_exempt = True
        return f
    return wrapper


def is_csrf_exempt(view):
    """Check if a view is exempt from CSRF protection."""
    return getattr(view, 'csrf_exempt', False)

# Initialize limiter for this blueprint
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    strategy="fixed-window",
)


def get_user_id_from_user():
    """Key function for user-based rate limiting on authenticated endpoints."""
    return (
        str(current_user.id) if current_user.is_authenticated else get_remote_address()
    )


auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["POST"])
@csrf_exempt()
@limiter.limit("5 per hour", key_func=get_remote_address)
def register():
    """Register a new user."""
    data = request.get_json()

    # Validate input
    email = data.get("email", "").strip()
    password = data.get("password", "")
    name = data.get("name", "").strip()

    # Check validation
    is_valid, message = validate_email(email)
    if not is_valid:
        return jsonify({"error": message}), 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({"error": message}), 400

    is_valid, message = validate_name(name)
    if not is_valid:
        return jsonify({"error": message}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    # Create new user
    user = User(
        email=email,
        name=name,
        is_approved=False,  # Requires admin approval
        is_admin=False,
    )
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()

        # FR-SEC-003: Do NOT automatically log in the user
        # Users must wait for admin approval before logging in
        # Removed: login_user(user)

        # Create response with user data and approval requirement notice
        response = make_response(
            jsonify(
                {
                    "message": "Registration successful. Your account requires admin approval before you can log in.",
                    "requires_approval": True,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "is_approved": user.is_approved,
                        "is_admin": user.is_admin,
                    },
                }
            ),
            201,
        )

        # FR-SEC-003: Do NOT set JWT cookie until user is approved
        # Removed: set_jwt_cookie(response, user)
        return response

    except Exception:
        db.session.rollback()
        return jsonify({"error": "Registration failed"}), 500


@auth.route("/login", methods=["GET"])
def login_page():
    """Handle GET requests to login (redirect from Flask-Login)."""
    # Redirect to home page where login modal is available
    from flask import redirect, url_for, request
    from urllib.parse import quote

    next_page = request.args.get("next", "")
    # Use url_for to generate proper URL with /pdf-renamer prefix
    index_url = url_for("main.index")
    return redirect(f"{index_url}?login=true&next={quote(next_page)}")


@auth.route("/login", methods=["POST"])
@csrf_exempt()
@limiter.limit("10 per minute", key_func=get_remote_address)
def login():
    """Login existing user and set JWT in HttpOnly cookie."""
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        # SEC-001 FIX: Check if user is approved before allowing login
        # Unapproved users cannot obtain JWT tokens or access protected resources
        if not user.is_approved:
            return jsonify(
                {
                    "error": "Account pending admin approval",
                    "message": "Your account is waiting for admin approval. You will be notified when it is approved.",
                }
            ), 403

        # Security: Regenerate session to prevent session fixation attacks
        # Clear old session data so Flask-Login creates a fresh session
        session.clear()

        login_user(user, remember=data.get("remember", False))
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Create response with user data
        response = make_response(
            jsonify(
                {
                    "message": "Login successful",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "is_approved": user.is_approved,
                        "is_admin": user.is_admin,
                    },
                }
            )
        )

        # Set JWT token in HttpOnly cookie for XSS protection
        set_jwt_cookie(response, user)
        return response

    return jsonify({"error": "Invalid email or password"}), 401


@auth.route("/logout", methods=["POST"])
@csrf_exempt()
@login_required
def logout():
    """Logout current user and clear JWT cookie."""
    logout_user()

    # Clear JWT cookie
    response = make_response(jsonify({"message": "Logged out successfully"}))
    clear_jwt_cookie(response)
    return response


@auth.route("/me", methods=["GET"])
@auth_required
def get_current_user():
    """Get current user info."""
    return jsonify(
        {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "is_approved": current_user.is_approved,
                "is_admin": current_user.is_admin,
                "created_at": current_user.created_at.isoformat(),
                "last_login": current_user.last_login.isoformat()
                if current_user.last_login
                else None,
            }
        }
    )


@auth.route("/change-password", methods=["POST"])
@csrf_exempt()
@login_required
@limiter.limit("3 per hour", key_func=get_user_id_from_user)
def change_password():
    """Change user password."""
    data = request.get_json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Current and new passwords required"}), 400

    # Verify current password
    if not current_user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect"}), 400

    # Validate new password
    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({"error": message}), 400

    # Update password
    current_user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Password changed successfully"})


@auth.route("/update-profile", methods=["POST"])
@csrf_exempt()
@login_required
@limiter.limit("20 per hour", key_func=get_user_id_from_user)
def update_profile():
    """Update user profile information."""
    data = request.get_json()
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400

    # Validate name
    is_valid, message = validate_name(name)
    if not is_valid:
        return jsonify({"error": message}), 400

    # Update user
    current_user.name = name
    db.session.commit()

    return jsonify(
        {
            "message": "Profile updated successfully",
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "is_approved": current_user.is_approved,
                "is_admin": current_user.is_admin,
            },
        }
    )


@auth.route("/update-settings", methods=["POST"])
@csrf_exempt()
@login_required
@limiter.limit("20 per hour", key_func=get_user_id_from_user)
def update_settings():
    """Update user preferences."""
    data = request.get_json()

    # Get settings
    filename_format = data.get("filename_format", "Author_Year_Journal_Keywords")
    custom_format = data.get("custom_filename_format", "").strip()
    auto_download = data.get("auto_download", True)

    # Validate filename format
    valid_formats = [
        "Author_Year_Journal_Keywords",
        "Author_Year_Title",
        "Author_Year_Journal",
        "Year_Author_Title",
        "Custom",
    ]
    if filename_format not in valid_formats:
        return jsonify({"error": "Invalid filename format"}), 400

    # If custom format, validate it
    if filename_format == "Custom":
        if not custom_format:
            return jsonify(
                {"error": "Custom format is required when Custom is selected"}
            ), 400

        # Basic validation for custom format variables
        valid_vars = ["{author}", "{year}", "{title}", "{journal}", "{keywords}"]
        if not any(var in custom_format for var in valid_vars):
            return jsonify(
                {
                    "error": "Custom format must include at least one variable: "
                    + ", ".join(valid_vars)
                }
            ), 400

    # Update user preferences
    current_user.filename_format = filename_format
    current_user.custom_filename_format = (
        custom_format if filename_format == "Custom" else None
    )
    current_user.auto_download = auto_download

    db.session.commit()

    return jsonify(
        {
            "message": "Settings updated successfully",
            "settings": {
                "filename_format": current_user.filename_format,
                "custom_filename_format": current_user.custom_filename_format,
                "auto_download": current_user.auto_download,
            },
        }
    )


@auth.route("/settings", methods=["GET"])
@login_required
def get_settings():
    """Get user preferences."""
    return jsonify(
        {
            "settings": {
                "filename_format": current_user.filename_format,
                "custom_filename_format": current_user.custom_filename_format,
                "auto_download": current_user.auto_download,
            }
        }
    )


@auth.route("/refresh-token", methods=["POST"])
@csrf_exempt()
def refresh_token():
    """Refresh JWT token if user has been active and token is approaching expiration."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or len(auth_header) < 7 or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization token required"}), 401

    token = auth_header[7:]
    if not token:
        return jsonify({"error": "Authorization token is empty"}), 401

    try:
        # Attempt to refresh the token
        new_token = refresh_token_if_needed(token)

        if new_token:
            return jsonify(
                {"message": "Token refreshed successfully", "token": new_token}
            )
        else:
            # QUAL-001 FIX: Return 204 No Content when token doesn't need refresh yet
            # This is more semantically correct than returning 200 with a message
            # Clients should interpret 204 as "current token is still valid, no refresh needed"
            return "", 204

    except Exception as e:
        print(f"Token refresh error: {e}")
        return jsonify({"error": "Token refresh failed"}), 401
