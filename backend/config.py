import os
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _get_or_create_secret_key():
    """Get existing SECRET_KEY from file or create a new one and persist it."""
    # Environment variable takes priority
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    # Path to persistent secret key file
    secret_key_file = os.path.join(basedir, "instance", ".secret_key")

    # Try to read existing key from file
    if os.path.exists(secret_key_file):
        try:
            with open(secret_key_file, "r") as f:
                return f.read().strip()
        except Exception:
            pass  # Fall through to generate new key

    # Generate new key and persist it
    new_key = secrets.token_hex(32)
    os.makedirs(os.path.dirname(secret_key_file), exist_ok=True)
    with open(secret_key_file, "w") as f:
        f.write(new_key)
    os.chmod(secret_key_file, 0o600)  # Read/write for owner only

    return new_key


class Config:
    """Base configuration."""

    # Use persistent SECRET_KEY (auto-generated and saved on first run)
    SECRET_KEY = _get_or_create_secret_key()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Application root for reverse proxy support
    # Configure via APPLICATION_ROOT environment variable
    # - Set to "/pdf-renamer" when using reverse proxy at /pdf-renamer/
    # - Leave empty (default) for direct access (localhost:5000, IP:5000, etc.)
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "")

    # Authentication/session inactivity timeout
    # Used for:
    # - Flask session expiration (page routes, Flask-Login)
    # - JWT cookie expiration (API + auto-login from cookie)
    INACTIVITY_TIMEOUT_MINUTES = int(os.environ.get("INACTIVITY_TIMEOUT_MINUTES", "30"))

    # Flask session lifetime (sliding; refreshed on activity)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=INACTIVITY_TIMEOUT_MINUTES)
    SESSION_REFRESH_EACH_REQUEST = True

    # Flask-Login "remember me" cookie duration. Keep aligned with inactivity policy to
    # avoid "never expires" behavior when users check "remember me".
    REMEMBER_COOKIE_DURATION = timedelta(minutes=INACTIVITY_TIMEOUT_MINUTES)

    # Session configuration - always use root path for cookies
    # When using APPLICATION_ROOT with middleware, cookies must use "/" path
    # to work correctly. The middleware handles the path prefix stripping.
    SESSION_COOKIE_PATH = "/"
    REMEMBER_COOKIE_PATH = "/"

    # Cookie security settings - prevent XSS and CSRF attacks
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookies
    REMEMBER_COOKIE_HTTPONLY = True  # Prevent JavaScript access to remember cookies
    SESSION_COOKIE_SECURE = (
        os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    )  # HTTPS only in production
    REMEMBER_COOKIE_SECURE = (
        os.environ.get("COOKIE_SECURE", "false").lower() == "true"
    )  # HTTPS only in production

    # Cookie settings for reverse proxy compatibility
    SESSION_COOKIE_DOMAIN = None  # Use default (current domain)
    REMEMBER_COOKIE_DOMAIN = None

    # CSRF protection - use Strict for state-changing operations
    # Lax allows cookies for top-level navigations, Strict requires same-site
    SESSION_COOKIE_SAMESITE = "Lax"  # Allow cookies for top-level navigations
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # LLM settings
    # Default to Ollama (local LLM) - can be overridden by environment variables or database settings
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
    LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.2")
    # Default Ollama URL (standard Ollama port is 11434, override with OLLAMA_URL env var)
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    API_KEY_FILE = os.environ.get("API_KEY_FILE", "APISetting.txt")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "instance", "app.db")


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    TESTING = False

    # SECRET_KEY is inherited from Config (uses persistent file or env var)
    # For production, you can override with environment variable


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    "development": DevelopmentConfig,
    "default": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
