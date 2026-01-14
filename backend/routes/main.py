from flask import (
    Blueprint,
    render_template,
    jsonify,
    current_app,
    request,
    redirect,
    url_for,
)
from flask_login import current_user, login_required
import jwt
from backend.utils.auth import auth_required, admin_required as auth_admin_required

main = Blueprint("main", __name__)


@main.route("/")
def index():
    """Serve the main application page."""
    return render_template("index.html")


@main.route("/api/limits")
def get_limits():
    """Get user's current upload limits."""
    from flask_login import AnonymousUserMixin
    from backend.models import User

    # First check if Flask-Login has a user (session-based auth)
    if current_user.is_authenticated and not isinstance(
        current_user, AnonymousUserMixin
    ):
        max_files = current_user.get_max_files()
        return jsonify(
            {
                "max_files_per_submission": max_files,
                "is_registered": True,
                "is_approved": current_user.is_approved,
                "is_admin": current_user.is_admin,
            }
        )

    # Then check for JWT token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = payload.get("user_id")
            if user_id:
                user = User.query.get(user_id)
                if user:
                    max_files = user.get_max_files()
                    return jsonify(
                        {
                            "max_files_per_submission": max_files,
                            "is_registered": True,
                            "is_approved": user.is_approved,
                            "is_admin": user.is_admin,
                        }
                    )
        except Exception:
            pass  # Invalid token, fall through to anonymous

    # Anonymous users: 5 files per submission
    return jsonify(
        {
            "max_files_per_submission": 5,
            "is_registered": False,
            "is_approved": False,
            "is_admin": False,
        }
    )


@main.route("/profile")
@auth_required
def profile():
    """User profile page."""
    return render_template("profile.html")


@main.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "version": "1.0.0"})


@main.route("/admin")
@login_required
def admin_panel():
    """Admin panel page."""
    if not current_user.is_admin:
        return redirect(url_for("main.index"))
    return render_template("admin.html")


@main.route("/terms")
def terms():
    """Terms and Conditions page."""
    from backend.models import SystemSettings

    contact_email = SystemSettings.get_setting("contact_email", "")
    return render_template("terms.html", contact_email=contact_email)


@main.route("/privacy")
def privacy():
    """Privacy Policy page."""
    from backend.models import SystemSettings

    contact_email = SystemSettings.get_setting("contact_email", "")
    return render_template("privacy.html", contact_email=contact_email)


@main.route("/contact")
def contact():
    """Contact page."""
    from backend.models import SystemSettings

    contact_email = SystemSettings.get_setting("contact_email", "")
    return render_template("contact.html", contact_email=contact_email)
