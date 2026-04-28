from functools import wraps
from flask import request, jsonify, current_app, g
from flask_login import current_user
from backend.models import User
import jwt
import datetime
import logging

# Configure logger for authentication
logger = logging.getLogger(__name__)


def auth_required(f):
    """Decorator to require authentication for API endpoints.

    Priority: 1. JWT cookie (HttpOnly, most secure), 2. Authorization header, 3. Flask-Login session

    This ensures JWT is the primary authentication method, with Flask-Login sessions
    as a fallback for compatibility. The dual auth system is maintained but JWT is preferred.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Fast path: session already authenticated for this request.
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        # Use proper logging instead of print statements
        logger.debug(f"auth_required check for endpoint {request.endpoint}")

        # Primary: Check for JWT token in HttpOnly cookie (most secure, prevents XSS)
        token = get_jwt_from_cookie()
        token_source = "cookie"
        if not token:
            # Secondary: Check Authorization header (backward compatibility)
            auth_header = request.headers.get("Authorization")
            # Validate header has content beyond "Bearer " prefix
            if (
                auth_header
                and len(auth_header) > 7
                and auth_header.startswith("Bearer ")
            ):
                token = auth_header[7:]
                token_source = "header"

        # If JWT token found, validate and authenticate
        if token:
            try:
                # Decode JWT token with proper expiration verification
                payload = jwt.decode(
                    token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
                )
                user_id = payload.get("user_id")
                logger.debug(
                    f"auth_required: JWT decoded from {token_source}, user_id: {user_id}"
                )

                if user_id:
                    from flask_login import login_user
                    from backend.database import db

                    user = db.session.get(User, user_id)
                    logger.debug(
                        f"auth_required: User found: {user}, approved: {user.is_approved if user else 'None'}"
                    )

                    if user and user.is_approved and user.is_active and user.deactivated_at is None:
                        # Set the user in Flask-Login for this request
                        logger.debug(
                            f"auth_required: Logging in user {user_id} via JWT ({token_source})"
                        )
                        login_user(user)
                        return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                # SEC-001 FIX: Do NOT allow fallback to session when JWT is expired
                # Expired tokens must always be rejected to prevent token abuse
                logger.warning(
                    f"auth_required: JWT token expired (from {token_source}) - rejecting expired token"
                )
                # REQ-AUTH-003: Clear invalid JWT cookie on expiration
                g.clear_jwt_cookie = True
                return jsonify({"error": "Token expired. Please log in again."}), 401
            except jwt.InvalidTokenError as e:
                # Catch all JWT-related errors (DecodeError, InvalidSignatureError, etc.)
                logger.warning(
                    f"auth_required: Invalid JWT token: {type(e).__name__} from {token_source}"
                )
                # REQ-AUTH-003: Clear invalid JWT cookie on invalid token
                g.clear_jwt_cookie = True
                # Do NOT fall through to session - return 401 immediately
                return jsonify({"error": "Invalid authentication token"}), 401
            except Exception as e:
                logger.warning(
                    f"JWT decode error: {str(e)[:100]}"
                )  # Limit error message length
                # REQ-AUTH-003: Clear invalid JWT cookie on decode error
                g.clear_jwt_cookie = True
                return jsonify({"error": "Authentication failed"}), 401

        # Fallback: Check Flask-Login session (for compatibility and page routes)
        if current_user.is_authenticated:
            logger.debug(
                f"auth_required: Flask-Login session valid for user {current_user.id}"
            )
            return f(*args, **kwargs)

        logger.debug(f"auth_required: Authentication failed for {request.endpoint}")
        return jsonify({"error": "Authentication required"}), 401

    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges."""

    @wraps(f)
    @auth_required
    def decorated_function(*args, **kwargs):
        logger.debug(
            f"admin_required check for user {current_user.id}, is_admin: {current_user.is_admin if current_user else 'None'}"
        )
        if not current_user.is_admin:
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)

    return decorated_function


def generate_token(user):
    """Generate JWT token for API access with inactivity-based expiration."""
    now = datetime.datetime.now(datetime.timezone.utc)
    inactivity_minutes = int(current_app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30))
    payload = {
        "user_id": user.id,
        "email": user.email,
        # Expire after inactivity timeout. Token is refreshed server-side on activity.
        "exp": now + datetime.timedelta(minutes=inactivity_minutes),
        "iat": now,  # Issued at time
        "last_activity": now.isoformat(),  # Track last activity
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def set_jwt_cookie(response, user):
    """Set JWT token in HttpOnly cookie for XSS protection."""
    token = generate_token(user)
    # Get cookie secure setting from config
    secure = current_app.config.get("SESSION_COOKIE_SECURE", False)
    inactivity_minutes = int(current_app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30))
    max_age = inactivity_minutes * 60
    # Set HttpOnly cookie to prevent XSS access
    response.set_cookie(
        "jwt_token",
        token,
        max_age=max_age,
        httponly=True,  # Prevent JavaScript access (critical for security)
        secure=secure,  # Only send over HTTPS in production
        samesite="Lax",  # CSRF protection
        path="/",  # Available across all paths
    )
    return response


def clear_jwt_cookie(response):
    """Clear JWT cookie on logout."""
    response.set_cookie(
        "jwt_token",
        "",
        expires=0,  # Immediately expire
        httponly=True,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        samesite="Lax",
        path="/",
    )
    return response


def get_jwt_from_cookie():
    """Get JWT token from HttpOnly cookie."""
    return request.cookies.get("jwt_token")


def refresh_token_if_needed(token):
    """Refresh token if valid and approaching expiration.

    Security improvements:
    - Validates token expiration (no verify_exp=False bypass)
    - Checks user is still active and approved
    - Enforces maximum token lifetime of 7 days
    """
    try:
        # Decode token WITH expiration verification (security fix)
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        exp_time = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)
        issued_at = datetime.datetime.fromtimestamp(payload.get("iat", 0), tz=datetime.timezone.utc)

        # Security: Enforce maximum token lifetime of 7 days from original issuance
        max_lifetime = datetime.timedelta(days=7)
        if now - issued_at > max_lifetime:
            logger.debug("Token refresh rejected: maximum lifetime exceeded")
            return None  # Token too old, require re-authentication

        # If token expires soon, refresh it.
        # Keep this threshold smaller than the inactivity timeout so active users
        # don't get logged out due to timing jitter.
        inactivity_minutes = int(
            current_app.config.get("INACTIVITY_TIMEOUT_MINUTES", 30)
        )
        refresh_threshold_seconds = min(5 * 60, max(60, inactivity_minutes * 60 // 3))
        time_until_expiration = (exp_time - now).total_seconds()
        if time_until_expiration < refresh_threshold_seconds:
            from backend.database import db

            user = db.session.get(User, payload["user_id"])
            if not user:
                logger.debug("Token refresh rejected: user not found")
                return None

            # Security: Check user is still active and approved
            if not user.is_approved:
                logger.debug("Token refresh rejected: user not approved")
                return None

            # Security: Check if user has been deactivated (deactivated_at is not None)
            if user.deactivated_at is not None:
                logger.debug("Token refresh rejected: user deactivated")
                return None

            # Generate new token with updated expiration
            new_payload = {
                "user_id": user.id,
                "email": user.email,
                "exp": now + datetime.timedelta(minutes=inactivity_minutes),
                "iat": now,
                "last_activity": now.isoformat(),
            }
            return jwt.encode(
                new_payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256"
            )
    except jwt.ExpiredSignatureError:
        logger.debug("Token refresh rejected: token expired")
        return None  # Expired tokens cannot be refreshed (security fix)
    except Exception as e:
        logger.warning(
            f"Error refreshing token: {str(e)[:100]}"
        )  # Limit error message length
        return None

    return None
