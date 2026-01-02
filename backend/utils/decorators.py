from functools import wraps
from flask import request, g, jsonify
from flask_login import current_user
from datetime import datetime, timedelta
from backend.models import Usage, User
from backend.database import db
from backend.utils import auth_required

def track_usage(f):
    """Decorator to track API usage for both anonymous and authenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Store usage info in g for later use
        g.user_id = None
        g.ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        g.user_agent = request.headers.get('User-Agent', '')

        # Check Flask-Login current_user instead of request.current_user
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            g.user_id = current_user.id

        return f(*args, **kwargs)

    return decorated_function

def check_rate_limit(f):
    """Decorator to check if user has exceeded rate limits."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.user_id = getattr(g, 'user_id', None)
        g.ip_address = getattr(g, 'ip_address', request.remote_addr)

        # Get user limits
        if g.user_id:
            user = User.query.get(g.user_id)
            if user:
                # Use user-specific file limits from database
                max_files = user.get_max_files()
                max_submissions = 10 if user.is_approved else 5
            else:
                max_files = 5   # Fallback for safety
                max_submissions = 5
        else:
            max_files = 5   # Anonymous users
            max_submissions = 5  # 5 times per day

        # Check recent usage
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        if g.user_id:
            # Check registered user usage
            recent_usage = Usage.query.filter(
                Usage.user_id == g.user_id,
                Usage.timestamp > day_ago
            ).count()

            if recent_usage >= max_submissions:
                if user and user.is_approved:
                    message = f'Approved users can only submit files {max_submissions} times per day'
                else:
                    message = f'Users can only submit files {max_submissions} times per day. Contact admin for higher limits.'
                return jsonify({
                    'error': 'Usage limit exceeded',
                    'message': message
                }), 429

        else:
            # Check anonymous usage by IP
            ip_usage = Usage.query.filter(
                Usage.user_id.is_(None),
                Usage.ip_address == g.ip_address,
                Usage.timestamp > day_ago
            ).count()

            if ip_usage >= max_submissions:  # 5 times per day for anonymous
                return jsonify({
                    'error': 'Usage limit exceeded',
                    'message': f'Anonymous users can only submit files {max_submissions} times per day. Register for higher limits.'
                }), 429

        g.max_files = max_files
        return f(*args, **kwargs)

    return decorated_function

def log_usage(files_processed: int):
    """Decorator to record usage in database."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)

            # Log the usage
            try:
                usage = Usage(
                    user_id=getattr(g, 'user_id', None),
                    ip_address=getattr(g, 'ip_address', request.remote_addr),
                    user_agent=getattr(g, 'user_agent', ''),
                    files_processed=files_processed
                )
                db.session.add(usage)
                db.session.commit()
            except Exception as e:
                print(f"Error logging usage: {e}")

            return result
        return decorated_function
    return decorator

def record_usage(files_processed: int, user_id=None):
    """Direct function to record usage in database (call after processing)."""
    try:
        usage = Usage(
            user_id=user_id,
            ip_address=request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            user_agent=request.headers.get('User-Agent', ''),
            files_processed=files_processed
        )
        db.session.add(usage)
        db.session.commit()
        print(f"[DEBUG] Usage recorded: {files_processed} files for user {user_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Error logging usage: {e}")
        db.session.rollback()
        return False