from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from backend.models import User, Usage
from backend.database import db
from backend.utils.auth import admin_required
from datetime import datetime, timedelta

admin = Blueprint('admin', __name__)

@admin.route('/pending', methods=['GET'])
@admin_required
def get_pending_users():
    """Get list of users pending approval."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pending_users = User.query.filter_by(
        is_approved=False,
        is_admin=False
    ).order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    users_data = []
    for user in pending_users.items:
        # Get usage statistics for this user
        total_submissions = Usage.query.filter_by(user_id=user.id).count()
        total_files = Usage.query.filter_by(user_id=user.id).with_entities(
            db.func.sum(Usage.files_processed)
        ).scalar() or 0

        # Get recent activity (last 5 submissions)
        recent_activity = Usage.query.filter_by(user_id=user.id).order_by(
            Usage.timestamp.desc()
        ).limit(5).all()

        recent_activity_data = [{
            'timestamp': activity.timestamp.isoformat(),
            'files_processed': activity.files_processed,
            'ip_address': activity.ip_address,
            'success': activity.success
        } for activity in recent_activity]

        users_data.append({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'is_approved': user.is_approved,
            'is_admin': user.is_admin,
                'is_active': user.is_user_active(),
            'deactivated_at': user.deactivated_at.isoformat() if hasattr(user, 'deactivated_at') and user.deactivated_at else None,
            # User preferences
            'preferences': {
                'filename_format': user.filename_format,
                'custom_filename_format': user.custom_filename_format,
                'auto_download': user.auto_download
            },
            # Usage statistics
            'usage_stats': {
                'total_submissions': total_submissions,
                'total_files_processed': total_files,
                'max_files_per_submission': user.get_max_files(),
                'recent_activity': recent_activity_data
            }
        })

    return jsonify({
        'users': users_data,
        'total': pending_users.total,
        'pages': pending_users.pages,
        'current_page': page
    })

@admin.route('/approve/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Approve a user registration."""
    user = User.query.get_or_404(user_id)

    if user.is_approved:
        return jsonify({'error': 'User is already approved'}), 400

    user.is_approved = True
    db.session.commit()

    return jsonify({
        'message': f'User {user.email} has been approved',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_approved': user.is_approved
        }
    })

@admin.route('/reject/<int:user_id>', methods=['DELETE'])
@admin_required
def reject_user(user_id):
    """Reject and delete a user registration."""
    user = User.query.get_or_404(user_id)

    # Don't allow deletion of admins
    if user.is_admin:
        return jsonify({'error': 'Cannot delete admin user'}), 403

    # Store user info for response
    user_info = {
        'id': user.id,
        'email': user.email,
        'name': user.name
    }

    # Delete user and their usage logs
    Usage.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'message': f'User {user_info["email"]} has been rejected and deleted',
        'user': user_info
    })

@admin.route('/deactivate/<int:user_id>', methods=['POST'])
@admin_required
def deactivate_user(user_id):
    """Deactivate a user account."""
    user = User.query.get_or_404(user_id)

    # Don't allow deactivation of admins
    if user.is_admin:
        return jsonify({'error': 'Cannot deactivate admin user'}), 403

    if not user.is_active:
        return jsonify({'error': 'User is already deactivated'}), 400

    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': f'User {user.email} has been deactivated',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_active': user.is_active,
            'deactivated_at': user.deactivated_at.isoformat() if user.deactivated_at else None
        }
    })

@admin.route('/activate/<int:user_id>', methods=['POST'])
@admin_required
def activate_user(user_id):
    """Activate a previously deactivated user account."""
    user = User.query.get_or_404(user_id)

    # Don't allow activation of admins
    if user.is_admin:
        return jsonify({'error': 'Cannot modify admin user'}), 403

    if user.is_active:
        return jsonify({'error': 'User is already active'}), 400

    user.is_active = True
    user.deactivated_at = None
    db.session.commit()

    return jsonify({
        'message': f'User {user.email} has been activated',
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_active': user.is_active,
            'deactivated_at': user.deactivated_at
        }
    })

@admin.route('/delete/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Permanently delete a user account and all associated data."""
    user = User.query.get_or_404(user_id)

    # Don't allow deletion of admins
    if user.is_admin:
        return jsonify({'error': 'Cannot delete admin user'}), 403

    # Store user info for response
    user_info = {
        'id': user.id,
        'email': user.email,
        'name': user.name
    }

    # Delete user and their usage logs
    Usage.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'message': f'User {user_info["email"]} has been permanently deleted',
        'user': user_info
    })

@admin.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users with pagination and filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')  # 'approved', 'pending', 'all'

    query = User.query

    # Apply search filter
    if search:
        query = query.filter(
            (User.email.ilike(f'%{search}%')) |
            (User.name.ilike(f'%{search}%'))
        )

    # Apply status filter
    if status == 'approved':
        query = query.filter(User.is_approved == True)
    elif status == 'pending':
        query = query.filter(User.is_approved == False, User.is_admin == False)

    # Exclude admins unless specifically requested
    if status != 'admin':
        query = query.filter(User.is_admin == False)

    users = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    users_data = []
    for user in users.items:
        # Get usage statistics for this user
        total_submissions = Usage.query.filter_by(user_id=user.id).count()
        total_files = Usage.query.filter_by(user_id=user.id).with_entities(
            db.func.sum(Usage.files_processed)
        ).scalar() or 0

        # Get recent activity (last 5 submissions)
        recent_activity = Usage.query.filter_by(user_id=user.id).order_by(
            Usage.timestamp.desc()
        ).limit(5).all()

        recent_activity_data = [{
            'timestamp': activity.timestamp.isoformat(),
            'files_processed': activity.files_processed,
            'ip_address': activity.ip_address,
            'success': activity.success
        } for activity in recent_activity]

        users_data.append({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_approved': user.is_approved,
            'is_admin': user.is_admin,
                'is_active': user.is_user_active(),
            'deactivated_at': user.deactivated_at.isoformat() if hasattr(user, 'deactivated_at') and user.deactivated_at else None,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            # User preferences
            'preferences': {
                'filename_format': user.filename_format,
                'custom_filename_format': user.custom_filename_format,
                'auto_download': user.auto_download,
                'max_files_per_session': user.max_files_per_session
            },
            # Usage statistics
            'usage_stats': {
                'total_submissions': total_submissions,
                'total_files_processed': total_files,
                'max_files_per_submission': user.get_max_files(),
                'recent_activity': recent_activity_data
            }
        })

    return jsonify({
        'users': users_data,
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    })

@admin.route('/stats', methods=['GET'])
@admin_required
def get_admin_stats():
    """Get admin dashboard statistics."""
    # User statistics
    total_users = User.query.filter_by(is_admin=False).count()
    approved_users = User.query.filter_by(is_approved=True, is_admin=False).count()
    pending_users = User.query.filter_by(is_approved=False, is_admin=False).count()

    # Usage statistics
    last_month = datetime.utcnow() - timedelta(days=30)
    recent_usage = Usage.query.filter(Usage.timestamp > last_month).all()

    total_submissions = len(recent_usage)
    total_files = sum(u.files_processed for u in recent_usage)

    # Anonymous vs registered usage
    registered_usage = Usage.query.filter(
        Usage.timestamp > last_month,
        Usage.user_id.isnot(None)
    ).count()
    anonymous_usage = total_submissions - registered_usage

    # Top users
    top_users = db.session.query(
        User.name,
        User.email,
        db.func.sum(Usage.files_processed).label('total_files')
    ).join(Usage).filter(
        Usage.timestamp > last_month
    ).group_by(User.id).order_by(
        db.func.sum(Usage.files_processed).desc()
    ).limit(10).all()

    top_users_data = [{
        'name': name,
        'email': email,
        'files_processed': int(total_files)
    } for name, email, total_files in top_users]

    # Recent activity - get recent user registrations and status changes
    recent_activity = []

    # Get recent user registrations
    recent_users = User.query.filter(
        User.created_at > last_month
    ).order_by(User.created_at.desc()).limit(10).all()

    for user in recent_users:
        activity_type = "User Registration"
        description = f"{user.name} ({user.email})"

        if user.deactivated_at and user.deactivated_at > last_month:
            activity_type = "User Deactivated"
            description = f"{user.name} ({user.email})"
        elif user.is_approved and user.created_at < (datetime.utcnow() - timedelta(days=1)):
            # Check if user was approved recently (approximate)
            activity_type = "User Approved"
            description = f"{user.name} ({user.email})"

        recent_activity.append({
            'type': activity_type,
            'description': description,
            'timestamp': user.deactivated_at or user.created_at,
            'details': f"Status: {'Active' if user.is_user_active() else 'Inactive'}"
        })

    # Sort by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify({
        'user_stats': {
            'total_users': total_users,
            'approved_users': approved_users,
            'pending_users': pending_users
        },
        'usage_stats': {
            'total_submissions_last_month': total_submissions,
            'total_files_last_month': total_files,
            'registered_usage': registered_usage,
            'anonymous_usage': anonymous_usage
        },
        'top_users': top_users_data,
        'recent_activity': [{
            'type': activity['type'],
            'description': activity['description'],
            'timestamp': activity['timestamp'].isoformat(),
            'details': activity['details']
        } for activity in recent_activity]
    })

@admin.route('/cleanup', methods=['POST'])
@admin_required
def trigger_cleanup():
    """Manually trigger cleanup of old files."""
    from backend.services import FileService
    file_service = FileService()

    # Clean files older than 24 hours
    file_service.cleanup_temp_files(older_than_hours=24)

    return jsonify({'message': 'Cleanup completed successfully'})

@admin.route('/llm-settings', methods=['GET', 'POST'])
@admin_required
def manage_llm_settings():
    """Get or update LLM service settings."""
    from backend.models import SystemSettings
    import os

    if request.method == 'GET':
        # Get current LLM settings from database
        llm_settings = SystemSettings.get_llm_settings()

        # Also check for API key in environment or file as fallback
        openai_key_exists = llm_settings['openai_api_key_set']
        openai_key_masked = llm_settings['openai_api_key_masked']

        # Fallback: check environment variable or APISetting.txt
        if not openai_key_exists:
            env_key = os.environ.get('OPENAI_API_KEY')
            if env_key:
                openai_key_exists = True
                # Show first 4 and last 4 characters, use fixed 10 asterisks in the middle
                openai_key_masked = env_key[:4] + '*' * 10 + env_key[-4:] if len(env_key) > 8 else '*' * 10
            else:
                try:
                    with open('APISetting.txt', 'r') as f:
                        file_key = f.read().strip()
                        if file_key:
                            openai_key_exists = True
                            openai_key_masked = file_key[:4] + '*' * 10 + file_key[-4:] if len(file_key) > 8 else '*' * 10
                except FileNotFoundError:
                    pass

        return jsonify({
            'current_provider': llm_settings['provider'],
            'current_model': llm_settings['model'],
            'api_keys': {
                'openai': {
                    'is_set': openai_key_exists,
                    'masked': openai_key_masked
                }
            },
            'available_providers': {
                'openai': {
                    'name': 'OpenAI',
                    'models': ['gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo'],
                    'description': 'OpenAI API (requires API key)',
                    'requires_api_key': True
                },
                'ollama': {
                    'name': 'Ollama',
                    'models': ['llama2', 'codellama', 'mistral', 'vicuna'],
                    'description': 'Local Ollama server (requires setup)',
                    'requires_api_key': False
                }
            }
        })

    elif request.method == 'POST':
        data = request.get_json()
        provider = data.get('provider')
        model = data.get('model')
        api_key = data.get('api_key')

        # Validate provider
        valid_providers = ['openai', 'ollama']
        if provider not in valid_providers:
            return jsonify({'error': f'Invalid provider. Must be one of: {valid_providers}'}), 400

        # Validate model based on provider
        if provider == 'openai':
            valid_models = ['gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo']
        elif provider == 'ollama':
            valid_models = ['llama2', 'codellama', 'mistral', 'vicuna']
        else:
            valid_models = []

        if model not in valid_models:
            return jsonify({'error': f'Invalid model for provider {provider}. Valid models: {valid_models}'}), 400

        # For OpenAI, check if API key exists (either new one provided or existing one in DB/file)
        if provider == 'openai' and not api_key:
            # Check if key already exists in database
            if not SystemSettings.has_api_key('openai'):
                # Check environment variable
                if not os.environ.get('OPENAI_API_KEY'):
                    # Check APISetting.txt file
                    try:
                        with open('APISetting.txt', 'r') as f:
                            if not f.read().strip():
                                return jsonify({'error': 'API key required for OpenAI provider'}), 400
                    except FileNotFoundError:
                        return jsonify({'error': 'API key required for OpenAI provider'}), 400

        # Save settings to database
        user_id = current_user.id if current_user.is_authenticated else None

        # Always update provider and model
        SystemSettings.set_llm_provider(provider, user_id=user_id)
        SystemSettings.set_llm_model(model, user_id=user_id)

        # Only update API key if a new one was provided
        if api_key and api_key.strip():
            SystemSettings.set_api_key('openai', api_key.strip(), user_id=user_id)

            # Also save to APISetting.txt for backward compatibility
            try:
                with open('APISetting.txt', 'w') as f:
                    f.write(api_key.strip())
            except Exception as e:
                print(f"Warning: Could not save API key to file: {e}")

        # Update Flask config for current session
        from flask import current_app
        current_app.config['LLM_PROVIDER'] = provider
        current_app.config['LLM_MODEL'] = model

        # Get masked key for response
        masked_key = SystemSettings.get_masked_api_key('openai')

        return jsonify({
            'message': 'LLM settings updated successfully',
            'settings': {
                'provider': provider,
                'model': model,
                'api_key_masked': masked_key
            }
        })

@admin.route('/system-status')
@admin_required
def system_status():
    """Get system status and health information."""
    from datetime import datetime, timedelta
    import os
    import sys

    # Database status
    try:
        # Simple query to test database connection
        db.session.query(User).first()
        db_status = 'healthy'
        db_error = None
    except Exception as e:
        db_status = 'error'
        db_error = str(e)

    # LLM service status
    llm_status = 'unknown'
    llm_error = None
    try:
        from flask import current_app
        config = current_app.config
        from backend.services import LLMService
        llm_service = LLMService(config)
        # Test connection (for OpenAI)
        if llm_service.provider == 'openai':
            llm_service.client.models.list()
            llm_status = 'healthy'
    except Exception as e:
        llm_status = 'error'
        llm_error = str(e)

    # Storage status
    storage_status = 'unknown'
    try:
        import shutil
        total, used, free = shutil.disk_usage('.')
        storage_status = {
            'total_gb': round(total / (1024**3), 2),
            'used_gb': round(used / (1024**3), 2),
            'free_gb': round(free / (1024**3), 2),
            'usage_percent': round((used / total) * 100, 2)
        }
    except Exception as e:
        storage_status = {'error': str(e)}

    # System info
    system_info = {
        'python_version': sys.version,
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'app_version': '1.0.0'
    }

    return jsonify({
        'database': {
            'status': db_status,
            'error': db_error
        },
        'llm_service': {
            'status': llm_status,
            'error': llm_error
        },
        'storage': storage_status,
        'system': system_info,
        'timestamp': datetime.utcnow().isoformat()
    })

@admin.route('/users/<int:user_id>/limits', methods=['PUT'])
@admin_required
def update_user_limits(user_id):
    """Update user file limits."""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        # Prevent modifying admin users' limits (except by other admins)
        if user.is_admin and not current_user.is_admin:
            return jsonify({'error': 'Cannot modify admin user limits'}), 403

        # Validate max_files_per_session
        max_files = data.get('max_files_per_session')
        if max_files is None:
            return jsonify({'error': 'max_files_per_session is required'}), 400

        # Validate range
        if not isinstance(max_files, int) or max_files < 1 or max_files > 1000:
            return jsonify({'error': 'max_files_per_session must be between 1 and 1000'}), 400

        # Update user limit
        user.max_files_per_session = max_files
        db.session.commit()

        return jsonify({
            'message': f'Updated file limit for {user.email} to {max_files} files per session',
            'user_id': user.id,
            'email': user.email,
            'max_files_per_session': user.max_files_per_session
        })

    except Exception as e:
        return jsonify({'error': f'Failed to update user limits: {str(e)}'}), 500