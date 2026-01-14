from flask import Flask, request, g
from flask_login import LoginManager, current_user
from backend.config import config
from backend.database import db
from backend.models import User, Usage, SystemSettings
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import datetime


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

# Debug: Verify API key is loaded
api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
if api_key:
    print(f"[Init] OPENAI_COMPATIBLE_API_KEY loaded: {api_key[:10]}...{api_key[-4:]}")
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

    # Initialize database monitoring middleware in production
    if not app.debug:
        from backend.middleware.db_monitor import DatabaseMonitorMiddleware

        DatabaseMonitorMiddleware(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

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
