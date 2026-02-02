from flask import Flask, request, jsonify
from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from backend.config import config
from backend.database import db
from backend.models import User, SystemSettings
from werkzeug.middleware.proxy_fix import ProxyFix
import os


def get_user_id_from_user():
    """Key function for user-based rate limiting."""
    return (
        str(current_user.id) if current_user.is_authenticated else get_remote_address()
    )


class ApplicationRootMiddleware:
    """
    WSGI middleware that strips APPLICATION_ROOT from incoming request paths.

    This allows Flask to handle requests that come through a reverse proxy
    with a prefix (e.g., /pdf-renamer) without needing to register routes
    with that prefix.

    For example:
    - Incoming request: /pdf-renamer/api/download/file.pdf
    - After middleware: /api/download/file.pdf
    - Flask routes match: @app.route('/api/download/<filename>')
    """

    def __init__(self, app, application_root=""):
        self.app = app
        self.application_root = application_root

    def __call__(self, environ, start_response):
        # Strip the APPLICATION_ROOT prefix from PATH_INFO if present
        if self.application_root and self.application_root != "/":
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(self.application_root):
                # Update PATH_INFO to remove the prefix
                environ["PATH_INFO"] = path_info[len(self.application_root) :]
                # Store the original prefix for use in URL generation
                environ["SCRIPT_NAME"] = self.application_root

        # Update REQUEST_URI if it exists (used by some WSGI servers)
        if (
            "REQUEST_URI" in environ
            and self.application_root
            and self.application_root != "/"
        ):
            request_uri = environ["REQUEST_URI"]
            if request_uri.startswith(self.application_root):
                environ["REQUEST_URI"] = request_uri[len(self.application_root) :]

        # Call the actual Flask app
        return self.app(environ, start_response)


# Load environment variables from .env file at project root
# This ensures API keys and config are available even when Flask auto-reloads
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# Debug: Verify API key is loaded (SEC-002: Do not log actual key characters)
api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
if api_key:
    print("[Init] OPENAI_COMPATIBLE_API_KEY loaded successfully")
else:
    print("[Init] WARNING: OPENAI_COMPATIBLE_API_KEY not found in environment")


def _load_llm_settings(app, db):
    """Load LLM settings from database into app config on startup."""
    try:
        # Get LLM provider and model from database
        provider = SystemSettings.get_setting("llm_provider")
        model = SystemSettings.get_setting("llm_model")
        ollama_url = SystemSettings.get_setting("ollama_url")

        # Set defaults if not in database
        if not provider:
            provider = os.environ.get("LLM_PROVIDER", "openai")
        if not model:
            model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        if not ollama_url:
            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        # Update app config
        app.config["LLM_PROVIDER"] = provider
        app.config["LLM_MODEL"] = model
        app.config["OLLAMA_URL"] = ollama_url

        print(f"[Init] LLM settings loaded: provider={provider}, model={model}")
    except Exception as e:
        print(f"[Warning] Could not load LLM settings from database: {e}")
        # Set defaults
        app.config["LLM_PROVIDER"] = os.environ.get("LLM_PROVIDER", "openai")
        app.config["LLM_MODEL"] = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        app.config["OLLAMA_URL"] = os.environ.get(
            "OLLAMA_URL", "http://localhost:11434"
        )


def create_app(config_name=None):
    # Get the absolute path to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "frontend", "templates"),
        static_folder=os.path.join(project_root, "frontend", "static"),
    )

    # Load configuration
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    # Detect database type from DATABASE_URL for optimized configuration
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgresql://"):
        config_name = "postgresql"  # Use PostgreSQL-specific config

    app.config.from_object(config[config_name])

    # Apply middleware in the correct order (outermost first, wraps inner)
    # 1. ApplicationRootMiddleware: Strips APPLICATION_ROOT prefix from incoming paths
    # 2. ProxyFix: Handles X-Forwarded headers for reverse proxy
    application_root = app.config.get("APPLICATION_ROOT", "")
    app.wsgi_app = ApplicationRootMiddleware(app.wsgi_app, application_root)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

    # Initialize extensions with engine options
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."

    # Initialize CSRF protection
    # Note: API endpoints using JWT cookies are exempt (cookies have SameSite protection)
    from flask_wtf.csrf import CSRFProtect, CSRFError

    # Custom CSRFProtect that exempts API routes
    class APIExemptCSRFProtect(CSRFProtect):
        def protect(self):
            # Skip CSRF for API routes - JWT cookies provide protection
            if request.path.startswith('/api/'):
                return
            return super().protect()

    csrf = APIExemptCSRFProtect(app)

    # CSRF error handler - handle CSRF errors gracefully
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        # For API routes, return JSON error instead of HTML
        if request.path.startswith('/api/'):
            return jsonify({"error": "CSRF validation failed"}), 400
        return e

    # Initialize Flask-Talisman for security headers (FR-SEC-001)
    # Adds HSTS, X-Frame-Options, X-Content-Type-Options, CSP headers
    from flask_talisman import Talisman

    # Determine if HTTPS enforcement should be enabled
    # Development/Testing: force_https=False allows HTTP on localhost
    # Production: force_https=True enforces HTTPS redirects
    flask_env = os.environ.get("FLASK_ENV", "production")
    force_https = flask_env not in ["development", "testing"]

    Talisman(
        app,
        force_https=force_https,
        strict_transport_security=True,
        strict_transport_security_preload=True,
        strict_transport_security_max_age=31536000,
        session_cookie_secure=True,
        session_cookie_http_only=True,
        session_cookie_samesite="Lax",
        content_security_policy={
            "default-src": "'self'",
            "img-src": "'self' data: https:",
            "script-src": "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "font-src": "'self' https://cdnjs.cloudflare.com",
            "connect-src": "'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        },
    )

    # Note: API endpoints use JWT cookies with SameSite=Lax protection
    # CSRF tokens are automatically validated for form submissions
    # API routes are automatically handled since they don't use form data
    # No manual exemption needed - Flask-WTF handles this correctly

    # Initialize Flask-Limiter for rate limiting
    # PERF-001: Rate Limiting Storage Configuration
    #
    # Current: Uses in-memory storage (storage_uri="memory://")
    # - Pros: Simple, no external dependencies
    # - Cons: Limits reset on application restart, not shared across multiple workers
    #
    # Production Recommendations:
    # - For single-worker deployments: memory:// is acceptable
    # - For multi-worker deployments: Use Redis or Memcached for shared state
    # - Redis example: storage_uri="redis://localhost:6379"
    # - Memcached example: storage_uri="memcached://localhost:11211"
    #
    # To enable persistent rate limiting across restarts:
    # 1. Install Redis: pip install redis
    # 2. Set RATE_LIMIT_STORAGE_URL environment variable
    # 3. Update storage_uri to use: os.environ.get("RATE_LIMIT_STORAGE_URL", "memory://")
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
        strategy="fixed-window",
    )

    # Initialize database monitoring middleware in production
    if not app.debug:
        from backend.middleware.db_monitor import DatabaseMonitorMiddleware

        DatabaseMonitorMiddleware(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from backend.routes.main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    from backend.routes.auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint, url_prefix="/api/auth")

    from backend.routes.upload import upload as upload_blueprint

    app.register_blueprint(upload_blueprint, url_prefix="/api")

    from backend.routes.admin import admin as admin_blueprint

    app.register_blueprint(admin_blueprint, url_prefix="/api/admin")

    # Favicon route - serves from static folder
    @app.route("/favicon.ico")
    def favicon():
        from flask import send_from_directory

        return send_from_directory(
            os.path.join(app.root_path, "..", "frontend", "static"),
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {"error": "Internal server error"}, 500

    @app.errorhandler(413)
    def too_large(error):
        return {"error": "File too large"}, 413

    # Create tables
    with app.app_context():
        db.create_all()

        # Run database migrations for existing tables
        _run_migrations(db)

        # Load LLM settings from database into app config
        _load_llm_settings(app, db)

        # Create default admin user if not exists (only if ADMIN_CREATE env var is set)
        create_admin = os.environ.get("ADMIN_CREATE", "").lower() == "true"
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin_password = os.environ.get("ADMIN_PASSWORD", None)

        if (
            create_admin
            and admin_password
            and not User.query.filter_by(email=admin_email).first()
        ):
            admin = User(
                email=admin_email, name="Administrator", is_admin=True, is_approved=True
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f"[Setup] Admin user created: {admin_email}")
        elif create_admin and not admin_password:
            print(
                "[Warning] ADMIN_CREATE is set but ADMIN_PASSWORD is not provided. Skipping admin creation."
            )

    # Template context processor for version
    @app.context_processor
    def inject_version():
        try:
            from backend import __version__

            return dict(get_version=lambda: __version__)
        except ImportError:
            return dict(get_version=lambda: "0.2.1")

    return app


def _run_migrations(db):
    """Run manual migrations to add new columns to existing tables."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)

    # Check and add 'success' column to 'usage' table
    if "usage" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("usage")]
        if "success" not in columns:
            try:
                db.session.execute(
                    text("ALTER TABLE usage ADD COLUMN success BOOLEAN DEFAULT 1")
                )
                db.session.commit()
                print("[Migration] Added 'success' column to usage table")
            except Exception as e:
                print(
                    f"[Migration] Note: Could not add success column (may already exist): {e}"
                )
                db.session.rollback()

    # Check and add columns to 'system_settings' table if needed
    if "system_settings" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("system_settings")]
        # Add any new columns here as needed
        pass
