from flask import Blueprint, render_template, jsonify, current_app, request
from flask_login import current_user, login_required

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')

@main.route('/api/limits')
def get_limits():
    """Get user's current upload limits."""
    if current_user.is_authenticated and current_user.is_approved:
        # Approved registered users get their configured limits
        return jsonify({
            'max_files_per_submission': current_user.get_max_files(),
            'max_submissions_per_day': 10,
            'is_registered': True,
            'is_approved': True,
            'remaining_uses': 'Unlimited'
        })
    else:
        # Both anonymous users and unapproved registered users get the same limits
        if current_user.is_authenticated:
            # For unapproved users, check if they have a custom limit, otherwise use default
            max_files = current_user.get_max_files() if hasattr(current_user, 'max_files_per_session') else 5
        else:
            max_files = 5

        return jsonify({
            'max_files_per_submission': max_files,
            'max_submissions_per_day': 5,
            'is_registered': current_user.is_authenticated if current_user else False,
            'is_approved': False,
            'remaining_uses': current_user.is_authenticated and not current_user.is_approved and 'Pending approval' or None
        })

@main.route('/profile')
@login_required
def profile():
    """User profile page."""
    return render_template('profile.html')

@main.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0'
    })

@main.route('/admin')
@login_required
def admin_panel():
    """Admin panel page."""
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    return render_template('admin.html')

@main.route('/terms')
def terms():
    """Terms and Conditions page."""
    return render_template('terms.html')

@main.route('/api/admin/setup-needed')
def admin_setup_needed():
    """Check if admin setup is needed."""
    from backend.utils.admin_setup import check_admin_exists
    from backend.models import SystemSettings

    setup_complete = SystemSettings.get_setting('admin_setup_complete', 'false')
    admin_exists = check_admin_exists()

    return jsonify({
        'setup_needed': not admin_exists or setup_complete != 'true',
        'admin_exists': admin_exists,
        'setup_complete': setup_complete == 'true'
    })

@main.route('/api/admin/setup', methods=['POST'])
def setup_admin():
    """Create the first admin user."""
    from backend.utils.admin_setup import check_admin_exists, create_first_admin
    from backend.models import User
    from backend.utils import validate_email, validate_password, validate_name

    # Check if admin already exists
    if check_admin_exists():
        return jsonify({'error': 'Admin user already exists'}), 400

    # Get data from request
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    # Validate inputs
    is_valid, message = validate_email(email)
    if not is_valid:
        return jsonify({'error': message}), 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400

    is_valid, message = validate_name(name)
    if not is_valid:
        return jsonify({'error': message}), 400

    # Create admin
    try:
        if create_first_admin(email, password, name):
            # Log in the new admin
            admin = User.query.filter_by(email=email).first()
            from flask_login import login_user
            login_user(admin)

            # Generate token
            from backend.utils.auth import generate_token
            token = generate_token(admin)

            return jsonify({
                'message': 'Admin user created successfully',
                'user': {
                    'id': admin.id,
                    'email': admin.email,
                    'name': admin.name,
                    'is_admin': admin.is_admin,
                    'is_approved': admin.is_approved
                },
                'token': token
            }), 201
        else:
            return jsonify({'error': 'Failed to create admin user'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500