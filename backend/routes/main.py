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
from backend.utils.auth import auth_required
from backend.models import User
from backend.database import db

main = Blueprint("main", __name__)


@main.route("/")
def index():
    """Serve the main application page."""
    return render_template("index.html")


@main.route("/api/limits")
def get_limits():
    """Get user's current upload limits."""
    from flask_login import AnonymousUserMixin

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
                token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = payload.get("user_id")
            if user_id:
                user = db.session.get(User, user_id)
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
        except jwt.ExpiredSignatureError:
            # LOG-002: Specific JWT exception handling
            pass  # Expired token, fall through to anonymous
        except jwt.InvalidTokenError:
            # LOG-002: Specific JWT exception handling (covers DecodeError, InvalidSignatureError, etc.)
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
    """Health check endpoint with uptime, db status, and dependency info (REQ-OPS-001)."""
    from backend.utils.metrics_collector import MetricsCollector
    from backend.utils.db_health import check_database_health

    # Application version
    try:
        from backend import __version__
        version = __version__
    except ImportError:
        version = "0.2.1"

    # Uptime in seconds
    collector = MetricsCollector.get_instance()
    uptime_seconds = collector.get_uptime()

    # Database status
    db_health = check_database_health()
    db_status = {
        "status": db_health.get("status", "unknown"),
        "responsive": db_health.get("database_responsive", False),
        "response_time_ms": db_health.get("response_time_ms"),
    }

    # Dependency summary
    dependencies = {
        "database": db_status["status"],
    }

    # Overall status: degraded if any dependency is unhealthy
    overall_status = "healthy"
    if db_status["status"] not in ("healthy",):
        overall_status = "degraded" if db_status["responsive"] else "error"

    return jsonify({
        "status": overall_status,
        "version": version,
        "uptime_seconds": round(uptime_seconds, 2),
        "db_status": db_status,
        "dependencies": dependencies,
    })


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
