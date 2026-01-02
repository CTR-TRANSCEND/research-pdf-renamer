from functools import wraps
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from backend.models import User
import jwt
import datetime

def auth_required(f):
    """Decorator to require authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"[DEBUG] auth_required check for endpoint {request.endpoint}")
        print(f"[DEBUG] Flask-Login current_user: {current_user}, authenticated: {current_user.is_authenticated if current_user else 'None'}")

        # Check Flask-Login session first
        if current_user.is_authenticated:
            print(f"[DEBUG] auth_required: Flask-Login session valid for user {current_user.id}")
            return f(*args, **kwargs)

        # Check for JWT token in Authorization header
        auth_header = request.headers.get('Authorization')
        print(f"[DEBUG] auth_required: Authorization header: {auth_header[:20] + '...' if auth_header and len(auth_header) > 20 else auth_header}")
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                # Decode JWT token
                payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
                user_id = payload.get('user_id')
                print(f"[DEBUG] auth_required: JWT decoded, user_id: {user_id}")
                if user_id:
                    from flask_login import login_user
                    user = User.query.get(user_id)
                    print(f"[DEBUG] auth_required: User found: {user}, approved: {user.is_approved if user else 'None'}")
                    if user and user.is_approved:
                        # Set the user in Flask-Login for this request
                        print(f"[DEBUG] auth_required: Logging in user {user_id} via JWT")
                        login_user(user)
                        return f(*args, **kwargs)
            except Exception as e:
                print(f"[DEBUG] JWT decode error: {e}")
                pass

        print(f"[DEBUG] auth_required: Authentication failed for {request.endpoint}")
        return jsonify({'error': 'Authentication required'}), 401

    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    @auth_required
    def decorated_function(*args, **kwargs):
        print(f"[DEBUG] admin_required check for user {current_user.id}, is_admin: {current_user.is_admin if current_user else 'None'}")
        if not current_user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)

    return decorated_function

def generate_token(user):
    """Generate JWT token for API access with sliding expiration."""
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),  # 24 hours base expiration
        'iat': datetime.datetime.utcnow(),  # Issued at time
        'last_activity': datetime.datetime.utcnow().isoformat()  # Track last activity
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def refresh_token_if_needed(token):
    """Refresh token if user has been active and token is approaching expiration."""
    try:
        # Decode current token
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'], options={"verify_exp": False})
        now = datetime.datetime.utcnow()
        exp_time = datetime.datetime.fromtimestamp(payload['exp'])

        # If token expires in less than 30 minutes, refresh it
        time_until_expiration = (exp_time - now).total_seconds()
        if time_until_expiration < 30 * 60:  # 30 minutes
            user = User.query.get(payload['user_id'])
            if user:
                # Generate new token with updated expiration
                new_payload = {
                    'user_id': user.id,
                    'email': user.email,
                    'exp': now + datetime.timedelta(hours=24),
                    'iat': now,
                    'last_activity': now.isoformat()
                }
                return jwt.encode(new_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    except Exception as e:
        print(f"Error refreshing token: {e}")

    return None