from flask import Blueprint, request, jsonify
from flask_login import current_user
from backend.models import User, Usage
from backend.database import db
from backend.utils.auth import admin_required
from backend.utils.validators import validate_llm_server_url
from datetime import datetime, timedelta
import logging
import threading

admin = Blueprint("admin", __name__)

# Configure logger for this module
logger = logging.getLogger(__name__)

import time
from collections import OrderedDict

# PERF-003: Add caching for Ollama models
# PERF-002: Add cache size limits to prevent unbounded memory growth
_MAX_CACHE_SIZE = 100  # Maximum number of provider URLs to cache
_ollama_models_cache = (
    OrderedDict()
)  # {ollama_url: {"data": models, "timestamp": time}}
CACHE_TTL = 300  # 5 minutes
# PERF-001 FIX: Add threading Lock for thread-safe cache access
_cache_lock = threading.RLock()  # Use RLock for reentrant locking


@admin.route("/pending", methods=["GET"])
@admin_required
def get_pending_users():
    """Get list of users pending approval."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pending_users = (
        User.query.filter_by(is_approved=False, is_admin=False)
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # PERF-002: Get all user IDs for batch querying
    user_ids = [user.id for user in pending_users.items]

    # Batch fetch usage statistics for all users
    usage_stats = {}
    activities_by_user = {}
    if user_ids:
        # Get total submissions and files for all users in one query
        stats_query = (
            db.session.query(
                Usage.user_id,
                db.func.count(Usage.id).label("total_submissions"),
                db.func.sum(Usage.files_processed).label("total_files"),
            )
            .filter(Usage.user_id.in_(user_ids))
            .group_by(Usage.user_id)
            .all()
        )

        for stat in stats_query:
            usage_stats[stat.user_id] = {
                "total_submissions": stat.total_submissions,
                "total_files": stat.total_files or 0,
            }

        # Get recent activity for all users
        recent_activities = (
            db.session.query(Usage)
            .filter(Usage.user_id.in_(user_ids))
            .order_by(Usage.user_id, Usage.timestamp.desc())
            .all()
        )

        # Group recent activities by user (max 5 per user)
        activities_by_user = {}
        for activity in recent_activities:
            if activity.user_id not in activities_by_user:
                activities_by_user[activity.user_id] = []
            if len(activities_by_user[activity.user_id]) < 5:
                activities_by_user[activity.user_id].append(
                    {
                        "timestamp": activity.timestamp.isoformat(),
                        "files_processed": activity.files_processed,
                        "ip_address": activity.ip_address,
                        "success": activity.success,
                    }
                )

    users_data = []
    for user in pending_users.items:
        # Get usage statistics from pre-fetched data
        stats = usage_stats.get(user.id, {"total_submissions": 0, "total_files": 0})
        recent_activity_data = activities_by_user.get(user.id, [])

        users_data.append(
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_approved": user.is_approved,
                "is_admin": user.is_admin,
                "is_active": user.is_user_active(),
                "deactivated_at": user.deactivated_at.isoformat()
                if hasattr(user, "deactivated_at") and user.deactivated_at
                else None,
                # User preferences
                "preferences": {
                    "filename_format": user.filename_format,
                    "custom_filename_format": user.custom_filename_format,
                    "auto_download": user.auto_download,
                },
                # Usage statistics
                "usage_stats": {
                    "total_submissions": stats["total_submissions"],
                    "total_files_processed": stats["total_files"],
                    "max_files_per_submission": user.get_max_files(),
                    "recent_activity": recent_activity_data,
                },
            }
        )

    return jsonify(
        {
            "users": users_data,
            "total": pending_users.total,
            "pages": pending_users.pages,
            "current_page": page,
        }
    )


@admin.route("/approve/<int:user_id>", methods=["POST"])
@admin_required
def approve_user(user_id):
    """Approve a user registration."""
    user = User.query.get_or_404(user_id)

    # LOG-002: Fix race condition with atomic UPDATE
    result = User.query.filter_by(id=user_id, is_approved=False).update(
        {"is_approved": True}
    )

    if result == 0:
        return jsonify({"error": "User already approved or not found"}), 400

    db.session.commit()

    # Refresh user to get updated data
    user = db.session.get(User, user_id)

    # Handle race condition where user might have been deleted
    if not user:
        return jsonify({"error": "User not found after update"}), 404

    return jsonify(
        {
            "message": f"User {user.email} has been approved",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_approved": user.is_approved,
            },
        }
    )


@admin.route("/reject/<int:user_id>", methods=["DELETE"])
@admin_required
def reject_user(user_id):
    """Reject and delete a user registration."""
    user = User.query.get_or_404(user_id)

    # Don't allow deletion of admins
    if user.is_admin:
        return jsonify({"error": "Cannot delete admin user"}), 403

    # Store user info for response
    user_info = {"id": user.id, "email": user.email, "name": user.name}

    # Delete user and their usage logs
    Usage.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify(
        {
            "message": f"User {user_info['email']} has been rejected and deleted",
            "user": user_info,
        }
    )


@admin.route("/deactivate/<int:user_id>", methods=["POST"])
@admin_required
def deactivate_user(user_id):
    """Deactivate a user account."""
    user = User.query.get_or_404(user_id)

    # Don't allow deactivation of admins
    if user.is_admin:
        return jsonify({"error": "Cannot deactivate admin user"}), 403

    # LOG-001: Use is_user_active() method for consistency
    # Check if user is currently active (both approved and active flag is True)
    if not user.is_user_active():
        return jsonify({"error": "User is already deactivated or not approved"}), 400

    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "message": f"User {user.email} has been deactivated",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_active": user.is_active,
                "deactivated_at": user.deactivated_at.isoformat()
                if user.deactivated_at
                else None,
            },
        }
    )


@admin.route("/activate/<int:user_id>", methods=["POST"])
@admin_required
def activate_user(user_id):
    """Activate a previously deactivated user account."""
    user = User.query.get_or_404(user_id)

    # Don't allow activation of admins
    if user.is_admin:
        return jsonify({"error": "Cannot modify admin user"}), 403

    # LOG-001: Use is_user_active() method for consistency
    # Check if user is already active (both approved and active flag is True)
    if user.is_user_active():
        return jsonify({"error": "User is already active"}), 400

    user.is_active = True
    user.deactivated_at = None
    db.session.commit()

    return jsonify(
        {
            "message": f"User {user.email} has been activated",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_active": user.is_active,
                "deactivated_at": user.deactivated_at,
            },
        }
    )


@admin.route("/delete/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """Permanently delete a user account and all associated data."""
    user = User.query.get_or_404(user_id)

    # Don't allow deletion of admins
    if user.is_admin:
        return jsonify({"error": "Cannot delete admin user"}), 403

    # Store user info for response
    user_info = {"id": user.id, "email": user.email, "name": user.name}

    # Delete user and their usage logs
    Usage.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify(
        {
            "message": f"User {user_info['email']} has been permanently deleted",
            "user": user_info,
        }
    )


@admin.route("/users", methods=["GET"])
@admin_required
def get_all_users():
    """Get all users with pagination and filtering."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")
    status = request.args.get("status", "")  # 'approved', 'pending', 'all'

    query = User.query

    # Apply search filter
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    # Apply status filter
    if status == "approved":
        query = query.filter(User.is_approved.is_(True))
    elif status == "pending":
        query = query.filter(User.is_approved.is_(False), User.is_admin.is_(False))
    elif status == "admin":
        query = query.filter(User.is_admin.is_(True))

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Get all user IDs for batch querying
    user_ids = [user.id for user in users.items]

    # Batch fetch usage statistics for all users
    usage_stats = {}
    activities_by_user = {}
    if user_ids:
        # Get total submissions and files for all users in one query
        stats_query = (
            db.session.query(
                Usage.user_id,
                db.func.count(Usage.id).label("total_submissions"),
                db.func.sum(Usage.files_processed).label("total_files"),
            )
            .filter(Usage.user_id.in_(user_ids))
            .group_by(Usage.user_id)
            .all()
        )

        for stat in stats_query:
            usage_stats[stat.user_id] = {
                "total_submissions": stat.total_submissions,
                "total_files": stat.total_files or 0,
            }

        # Get recent activity for all users (batch query with window function would be ideal,
        # but we'll use subqueries for SQLite compatibility)
        recent_activities = (
            db.session.query(Usage)
            .filter(Usage.user_id.in_(user_ids))
            .order_by(Usage.user_id, Usage.timestamp.desc())
            .all()
        )

        # Group recent activities by user
        activities_by_user = {}
        for activity in recent_activities:
            if activity.user_id not in activities_by_user:
                activities_by_user[activity.user_id] = []
            if len(activities_by_user[activity.user_id]) < 5:
                activities_by_user[activity.user_id].append(
                    {
                        "timestamp": activity.timestamp.isoformat(),
                        "files_processed": activity.files_processed,
                        "ip_address": activity.ip_address,
                        "success": activity.success,
                    }
                )

    users_data = []
    for user in users.items:
        # Get usage statistics from pre-fetched data
        stats = usage_stats.get(user.id, {"total_submissions": 0, "total_files": 0})

        recent_activity_data = activities_by_user.get(user.id, [])

        users_data.append(
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_approved": user.is_approved,
                "is_admin": user.is_admin,
                "is_active": user.is_user_active(),
                "deactivated_at": user.deactivated_at.isoformat()
                if hasattr(user, "deactivated_at") and user.deactivated_at
                else None,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                # User preferences
                "preferences": {
                    "filename_format": user.filename_format,
                    "custom_filename_format": user.custom_filename_format,
                    "auto_download": user.auto_download,
                    "max_files_per_session": user.max_files_per_session,
                },
                # Usage statistics
                "usage_stats": {
                    "total_submissions": stats["total_submissions"],
                    "total_files_processed": stats["total_files"],
                    "max_files_per_submission": user.get_max_files(),
                    "recent_activity": recent_activity_data,
                },
            }
        )

    return jsonify(
        {
            "users": users_data,
            "total": users.total,
            "pages": users.pages,
            "current_page": page,
        }
    )


@admin.route("/stats", methods=["GET"])
@admin_required
def get_admin_stats():
    """Get admin dashboard statistics."""
    # User statistics - include all users including admins
    user_stats = db.session.query(
        db.func.count(User.id).label("total_users"),
        db.func.sum(db.case((User.is_approved.is_(True), 1), else_=0)).label(
            "approved_users"
        ),
        db.func.sum(db.case((User.is_approved.is_(False), 1), else_=0)).label(
            "pending_users"
        ),
        db.func.sum(db.case((User.is_admin.is_(True), 1), else_=0)).label(
            "admin_users"
        ),
    ).first()

    total_users = user_stats.total_users or 0
    approved_users = user_stats.approved_users or 0
    pending_users = user_stats.pending_users or 0
    admin_users = user_stats.admin_users or 0

    # Usage statistics - optimized with database aggregation
    last_month = datetime.utcnow() - timedelta(days=30)

    # Get all usage statistics in one query
    usage_stats = (
        db.session.query(
            db.func.count(Usage.id).label("total_submissions"),
            db.func.sum(Usage.files_processed).label("total_files"),
            db.func.sum(db.case((Usage.user_id.isnot(None), 1), else_=0)).label(
                "registered_submissions"
            ),
        )
        .filter(Usage.timestamp > last_month)
        .first()
    )

    total_submissions = usage_stats.total_submissions or 0
    total_files = usage_stats.total_files or 0
    registered_usage = usage_stats.registered_submissions or 0
    anonymous_usage = total_submissions - registered_usage

    # Top users
    top_users = (
        db.session.query(
            User.name,
            User.email,
            db.func.sum(Usage.files_processed).label("total_files"),
        )
        .join(Usage)
        .filter(Usage.timestamp > last_month)
        .group_by(User.id)
        .order_by(db.func.sum(Usage.files_processed).desc())
        .limit(10)
        .all()
    )

    top_users_data = [
        {"name": name, "email": email, "files_processed": int(total_files)}
        for name, email, total_files in top_users
    ]

    # Recent activity - get recent user registrations and status changes
    recent_activity = []

    # Get recent user registrations
    recent_users = (
        User.query.filter(User.created_at > last_month)
        .order_by(User.created_at.desc())
        .limit(10)
        .all()
    )

    for user in recent_users:
        activity_type = "User Registration"
        description = f"{user.name} ({user.email})"

        if user.deactivated_at and user.deactivated_at > last_month:
            activity_type = "User Deactivated"
            description = f"{user.name} ({user.email})"
        elif user.is_approved and user.created_at < (
            datetime.utcnow() - timedelta(days=1)
        ):
            # Check if user was approved recently (approximate)
            activity_type = "User Approved"
            description = f"{user.name} ({user.email})"

        recent_activity.append(
            {
                "type": activity_type,
                "description": description,
                "timestamp": user.deactivated_at or user.created_at,
                "details": f"Status: {'Active' if user.is_user_active() else 'Inactive'}",
            }
        )

    # Sort by timestamp
    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)

    return jsonify(
        {
            "user_stats": {
                "total_users": total_users,
                "approved_users": approved_users,
                "pending_users": pending_users,
                "admin_users": admin_users,
            },
            "usage_stats": {
                "total_submissions_last_month": total_submissions,
                "total_files_last_month": total_files,
                "registered_usage": registered_usage,
                "anonymous_usage": anonymous_usage,
            },
            "top_users": top_users_data,
            "recent_activity": [
                {
                    "type": activity["type"],
                    "description": activity["description"],
                    "timestamp": activity["timestamp"].isoformat(),
                    "details": activity["details"],
                }
                for activity in recent_activity
            ],
        }
    )


@admin.route("/cleanup", methods=["POST"])
@admin_required
def trigger_cleanup():
    """Manually trigger cleanup of old files."""
    from backend.services import FileService

    file_service = FileService()

    # Clean files older than 24 hours
    file_service.cleanup_temp_files(older_than_hours=24)

    return jsonify({"message": "Cleanup completed successfully"})


def _get_ollama_models(ollama_url, timeout=5):
    """Fetch available models from Ollama server.

    Args:
        ollama_url: The Ollama server URL
        timeout: Request timeout in seconds

    Returns:
        List of model names, or empty list if connection fails
    """
    import requests

    # NEW-003: Validate URL before use to prevent SSRF attacks
    is_valid, error_msg = validate_llm_server_url(ollama_url)
    if not is_valid:
        logger.warning(f"Invalid Ollama URL in _get_ollama_models: {error_msg}")
        return []

    # PERF-001 FIX: Use lock for thread-safe cache access
    with _cache_lock:
        # PERF-002: Check cache first with proper TTL validation
        now = time.time()
        if ollama_url in _ollama_models_cache:
            cached_entry = _ollama_models_cache[ollama_url]
            if now - cached_entry["timestamp"] < CACHE_TTL:
                # Move to end (mark as recently used) for LRU
                _ollama_models_cache.move_to_end(ollama_url)
                return cached_entry["data"]
            else:
                # Expired entry, remove it
                del _ollama_models_cache[ollama_url]

    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=timeout)
        response.raise_for_status()
        data = response.json()

        # Extract model names from response
        models = []
        if "models" in data:
            for model in data["models"]:
                # Model name format is usually "name:tag", we want just the name
                name = model.get("name", "")
                if ":" in name:
                    name = name.split(":")[0]
                if name:
                    models.append(name)

        # PERF-001 FIX: Use lock for thread-safe cache update
        with _cache_lock:
            # PERF-002: Update cache with LRU eviction if size exceeded
            _ollama_models_cache[ollama_url] = {"data": models, "timestamp": now}
            # Enforce max cache size by removing oldest entries
            while len(_ollama_models_cache) > _MAX_CACHE_SIZE:
                _ollama_models_cache.popitem(last=False)  # Remove oldest (first) entry

        return models
    except Exception as e:
        logger.info(f"Failed to fetch Ollama models from {ollama_url}: {e}")
        return []  # Return empty list to trigger frontend fetch


def _normalize_openai_compatible_url(server_url):
    # FIX-DIAG-001: Handle None case
    cleaned = (server_url or "").rstrip("/")
    if cleaned.endswith("/v1"):
        return cleaned[:-3]
    return cleaned


def _fetch_models_from_openai_compatible(ollama_url, headers, timeout=10):
    """Fetch models from OpenAI-compatible /v1/models endpoint.

    Args:
        ollama_url: Base server URL
        headers: Request headers (including optional Authorization)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (models_list, loaded_models_list) or (None, None) on failure
    """
    import requests

    # NEW-003: Validate URL before use to prevent SSRF attacks
    is_valid, error_msg = validate_llm_server_url(ollama_url)
    if not is_valid:
        logger.warning(
            f"Invalid URL in _fetch_models_from_openai_compatible: {error_msg}"
        )
        return None, None

    try:
        response = requests.get(
            f"{ollama_url}/v1/models", headers=headers, timeout=timeout
        )
        if response.status_code != 200:
            return None, None

        data = response.json()

        # Extract model names from OpenAI-compatible format
        models = []
        if "data" in data:
            for model in data["data"]:
                model_name = model.get("id", "")
                if model_name:
                    models.append(model_name)

        # Get loaded models from /models/status endpoint for LocalLLM
        loaded_models = []
        try:
            status_response = requests.get(
                f"{ollama_url}/models/status", headers=headers, timeout=5
            )
            if status_response.status_code == 200:
                status_data = status_response.json()
                if "loaded" in status_data:
                    for model in status_data["loaded"]:
                        # Add the base model name for matching
                        name = model.get("name", "")
                        if name:
                            loaded_models.append(name)
                        # Also add the ollama_name if different (for matching with /v1/models)
                        ollama_name = model.get("ollama_name", "")
                        if ollama_name and ollama_name not in loaded_models:
                            loaded_models.append(ollama_name)
                logger.info(f"Loaded models from /models/status: {loaded_models}")
        except Exception as e:
            logger.info(f"Failed to get loaded models from /models/status: {e}")

        return models, loaded_models
    except Exception as e:
        logger.info(f"Failed to fetch from /v1/models: {e}")
        return None, None


def _fetch_models_from_ollama_native(ollama_url, headers, timeout=10):
    """Fetch models from native Ollama /api/tags endpoint.

    Args:
        ollama_url: Base server URL
        headers: Request headers (including optional Authorization)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (models_list, loaded_models_list) or (None, None) on failure
    """
    import requests

    # NEW-003: Validate URL before use to prevent SSRF attacks
    is_valid, error_msg = validate_llm_server_url(ollama_url)
    if not is_valid:
        logger.warning(f"Invalid URL in _fetch_models_from_ollama_native: {error_msg}")
        return None, None

    try:
        response = requests.get(
            f"{ollama_url}/api/tags", headers=headers, timeout=timeout
        )
        if response.status_code != 200:
            return None, None

        data = response.json()

        # Extract model names from Ollama format (all available models)
        models = []
        if "models" in data:
            for model in data["models"]:
                name = model.get("name", "")
                if ":" in name:
                    name = name.split(":")[0]
                if name:
                    models.append(name)

        # Get loaded models (models currently in memory)
        loaded_models = []

        # First, try the native Ollama /api/ps endpoint
        ps_success = False
        try:
            ps_response = requests.get(
                f"{ollama_url}/api/ps", headers=headers, timeout=5
            )
            if ps_response.status_code == 200:
                ps_data = ps_response.json()
                if "models" in ps_data:
                    for model in ps_data["models"]:
                        name = model.get("name", "")
                        if ":" in name:
                            name = name.split(":")[0]
                        if name:
                            loaded_models.append(name)
                logger.info(f"Loaded models from /api/ps: {loaded_models}")
                ps_success = True
        except Exception as e:
            logger.info(f"Failed to get loaded models from /api/ps: {e}")

        # Fallback: If /api/ps didn't return any models or failed,
        # try the LocalLLM /models/status endpoint (works for LocalLLM servers)
        if not ps_success or not loaded_models:
            logger.info("Trying fallback endpoint /models/status for loaded models")
            try:
                status_response = requests.get(
                    f"{ollama_url}/models/status", headers=headers, timeout=5
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if "loaded" in status_data:
                        for model in status_data["loaded"]:
                            # Add the base model name for matching
                            name = model.get("name", "")
                            if name:
                                loaded_models.append(name)
                            # Also add the ollama_name if different (for matching with /api/tags)
                            ollama_name = model.get("ollama_name", "")
                            if ollama_name and ollama_name not in loaded_models:
                                loaded_models.append(ollama_name)
                    logger.info(f"Loaded models from /models/status: {loaded_models}")
            except Exception as e:
                logger.info(f"Failed to get loaded models from /models/status: {e}")

        return models, loaded_models
    except Exception as e:
        logger.info(f"Failed to fetch from /api/tags: {e}")
        return None, None


def _try_endpoint_with_fallback(
    ollama_url, primary_endpoint, fallback_endpoint, headers, timeout=10
):
    """Try primary endpoint with fallback to secondary endpoint.

    Args:
        ollama_url: Base server URL
        primary_endpoint: Primary endpoint path (e.g., "/v1/models")
        fallback_endpoint: Fallback endpoint path (e.g., "/api/tags")
        headers: Request headers (including optional Authorization)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, endpoint_type, response_json) or (False, None, None) on failure
        endpoint_type is either "openai-compatible" or "ollama-native"
    """
    import requests

    # NEW-003: Validate URL before use to prevent SSRF attacks
    is_valid, error_msg = validate_llm_server_url(ollama_url)
    if not is_valid:
        logger.warning(f"Invalid URL in _try_endpoint_with_fallback: {error_msg}")
        return False, None, None

    # Try primary endpoint first
    response = requests.get(
        f"{ollama_url}{primary_endpoint}", headers=headers, timeout=timeout
    )

    logger.info(f"{primary_endpoint} response status: {response.status_code}")
    if response.status_code != 200:
        logger.info(f"{primary_endpoint} response body: {response.text[:200]}")

    # Handle 401/403 authentication errors
    if response.status_code in (401, 403):
        return False, None, None

    if response.status_code == 200:
        endpoint_type = (
            "openai-compatible" if primary_endpoint == "/v1/models" else "ollama-native"
        )
        return True, endpoint_type, response.json()

    if response.status_code == 404:
        # Primary endpoint not found, try fallback endpoint
        logger.info(
            f"Primary endpoint {primary_endpoint} not found, trying {fallback_endpoint}"
        )
        response = requests.get(
            f"{ollama_url}{fallback_endpoint}", headers=headers, timeout=timeout
        )

        logger.info(f"{fallback_endpoint} response status: {response.status_code}")

        # Handle 401/403 authentication errors for fallback
        if response.status_code in (401, 403):
            return False, None, None

        if response.status_code == 200:
            endpoint_type = (
                "openai-compatible"
                if fallback_endpoint == "/v1/models"
                else "ollama-native"
            )
            return True, endpoint_type, response.json()

    return False, None, None


def _get_lm_studio_models():
    """Fetch available models from LM Studio server using native REST API."""
    from backend.models import SystemSettings
    import requests

    try:
        # Use LM Studio specific URL
        lm_studio_url = SystemSettings.get_provider_url("lm-studio")

        # NEW-003: Validate URL before use to prevent SSRF attacks
        if lm_studio_url:
            is_valid, error_msg = validate_llm_server_url(lm_studio_url)
            if not is_valid:
                logger.warning(f"Invalid LM Studio URL: {error_msg}")
                return {"models": [], "loaded_models": [], "jit_mode": False}

        # Ensure we have the base URL without /v1
        # FIX-DIAG-001: Handle None case for lm_studio_url
        base_url = (lm_studio_url or "").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

        # Try LM Studio's native REST API /api/v0/models (includes state information)
        response = requests.get(f"{base_url}/api/v0/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = []
            loaded_models = []

            if "data" in data:
                for model in data["data"]:
                    model_id = model.get("id", "")
                    state = model.get("state", "unknown")

                    # Filter out embedding models
                    if model_id and "embed" not in model_id.lower():
                        models.append(model_id)
                        # Track which models are loaded/ready
                        if state == "loaded":
                            loaded_models.append(model_id)

            return {
                "models": models,
                "loaded_models": loaded_models,
                "jit_mode": len(models)
                == len(loaded_models),  # If all models are loaded, JIT might be OFF
            }
        else:
            # Fallback to OpenAI-compatible endpoint if native API fails
            response = requests.get(f"{base_url}/v1/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = []
                if "data" in data:
                    for model in data["data"]:
                        model_id = model.get("id", "")
                        if model_id and "embed" not in model_id.lower():
                            models.append(model_id)
                return {
                    "models": models,
                    "loaded_models": models,  # Assume all are usable (JIT ON)
                    "jit_mode": True,
                }
    except Exception as e:
        logger.info(f"Failed to fetch LM Studio models: {e}")
    return {"models": [], "loaded_models": [], "jit_mode": False}


@admin.route("/llm-settings", methods=["GET", "POST"])
@admin_required
def manage_llm_settings():
    """Get or update LLM service settings."""
    from backend.models import SystemSettings
    import os

    if request.method == "GET":
        # Get current LLM settings from database
        llm_settings = SystemSettings.get_llm_settings()

        # Check API key from environment variable (primary source)
        openai_key_exists = False
        openai_key_source = "none"
        openai_key_masked = None
        openai_env_var = None

        # Priority 1: Environment variable (recommended)
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            openai_key_exists = True
            openai_key_source = "environment"
            openai_env_var = "OPENAI_API_KEY"
            # Sanitize the key to remove any trailing whitespace/special characters
            env_key = env_key.strip()
            # Show first 4 and last 4 characters
            openai_key_masked = (
                env_key[:4] + "*" * 10 + env_key[-4:] if len(env_key) > 8 else "*" * 10
            )
        else:
            # Priority 2: Check database (deprecated, but may exist)
            if llm_settings["openai_api_key_set"]:
                openai_key_exists = True
                openai_key_source = "database_deprecated"
                openai_key_masked = llm_settings["openai_api_key_masked"]

        # Check Ollama API key (optional)
        ollama_key_exists = False
        ollama_key_source = "none"
        ollama_key_masked = None
        ollama_env_var = None

        ollama_env_key = os.environ.get("OLLAMA_API_KEY")
        if ollama_env_key:
            ollama_key_exists = True
            ollama_key_source = "environment"
            ollama_env_var = "OLLAMA_API_KEY"
            # Sanitize the key to remove any trailing whitespace/special characters
            ollama_env_key = ollama_env_key.strip()
            ollama_key_masked = (
                ollama_env_key[:4] + "*" * 10 + ollama_env_key[-4:]
                if len(ollama_env_key) > 8
                else "*" * 10
            )

        # Check OpenAI-Compatible API key (optional)
        openai_compat_key_exists = False
        openai_compat_key_source = "none"
        openai_compat_key_masked = None
        openai_compat_env_var = None

        openai_compat_env_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
        if openai_compat_env_key:
            openai_compat_key_exists = True
            openai_compat_key_source = "environment"
            openai_compat_env_var = "OPENAI_COMPATIBLE_API_KEY"
            # Sanitize the key to remove any trailing whitespace/special characters
            openai_compat_env_key = openai_compat_env_key.strip()
            openai_compat_key_masked = (
                openai_compat_env_key[:4] + "*" * 10 + openai_compat_env_key[-4:]
                if len(openai_compat_env_key) > 8
                else "*" * 10
            )

        # Get Ollama URL and models
        ollama_url = llm_settings.get("ollama_url", "http://localhost:11434")

        # For Ollama provider, try to fetch models dynamically
        # For other providers or if fetch fails, use empty list (will be fetched on demand)
        ollama_models = []
        current_provider = llm_settings.get("provider", "openai")

        if current_provider == "ollama":
            # Try to fetch models, but don't block on failure
            ollama_models = _get_ollama_models(ollama_url)
            # If empty (connection failed), frontend will trigger fetch on user action

        # Get LM Studio models once to avoid duplicate API calls
        lm_studio_data = _get_lm_studio_models()

        return jsonify(
            {
                "current_provider": llm_settings["provider"],
                "current_model": llm_settings["model"],
                "ollama_url": ollama_url,
                "api_keys": {
                    "openai": {
                        "is_set": openai_key_exists,
                        "masked": openai_key_masked,
                        "source": openai_key_source,
                        "env_var": openai_env_var,
                    },
                    "ollama": {
                        "is_set": ollama_key_exists,
                        "masked": ollama_key_masked,
                        "source": ollama_key_source,
                        "env_var": ollama_env_var,
                    },
                    "openai-compatible": {
                        "is_set": openai_compat_key_exists,
                        "masked": openai_compat_key_masked,
                        "source": openai_compat_key_source,
                        "env_var": openai_compat_env_var,
                    },
                    "lm-studio": {
                        "is_set": openai_compat_key_exists,
                        "masked": openai_compat_key_masked,
                        "source": openai_compat_key_source,
                        "env_var": openai_compat_env_var,
                    },
                },
                "available_providers": {
                    "openai": {
                        "name": "OpenAI",
                        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"],
                        "description": "OpenAI API (set via OPENAI_API_KEY environment variable)",
                        "requires_api_key": True,
                    },
                    "ollama": {
                        "name": "Ollama",
                        "models": ollama_models,
                        "description": "Native Ollama server (API key optional)",
                        "requires_api_key": False,
                        "url": SystemSettings.get_provider_url("ollama"),
                    },
                    "openai-compatible": {
                        "name": "OpenAI-Compatible",
                        "models": [],
                        "description": "OpenAI-compatible server like LocalLLM (API key optional)",
                        "requires_api_key": False,
                        "url": SystemSettings.get_provider_url("openai-compatible"),
                    },
                    "lm-studio": {
                        "name": "LM Studio",
                        "models": lm_studio_data.get("models", []),
                        "loaded_models": lm_studio_data.get("loaded_models", []),
                        "jit_mode": lm_studio_data.get("jit_mode", True),
                        "description": "LM Studio server (OpenAI-compatible, no API key required)",
                        "requires_api_key": False,
                        "url": SystemSettings.get_provider_url("lm-studio"),
                        "context_window": SystemSettings.get_setting(
                            "lm_studio_context_window", 4096
                        ),
                    },
                },
            }
        )

    elif request.method == "POST":
        data = request.get_json()
        provider = data.get("provider")
        model = data.get("model")
        api_key = data.get("api_key")
        ollama_url = data.get("ollama_url", "").strip()
        context_window = data.get("context_window")

        # Validate provider
        valid_providers = ["openai", "ollama", "openai-compatible", "lm-studio"]
        if provider not in valid_providers:
            return jsonify(
                {"error": f"Invalid provider. Must be one of: {valid_providers}"}
            ), 400

        # Validate model based on provider
        if provider == "openai":
            valid_models = ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]
            if model not in valid_models:
                return jsonify(
                    {
                        "error": f"Invalid model for provider {provider}. Valid models: {valid_models}"
                    }
                ), 400
        # For Ollama and OpenAI-Compatible, we allow any model name (will be validated by server)

        # Handle API key based on provider
        if provider == "openai":
            # Reject API key storage for OpenAI - must use environment variable
            if api_key and api_key.strip():
                return jsonify(
                    {
                        "error": "API key storage via web interface is deprecated for security.",
                        "message": "Please set the OPENAI_API_KEY environment variable instead.",
                        "instructions": [
                            "1. Create or edit the .env file in the project root",
                            "2. Add: OPENAI_API_KEY=your_api_key_here",
                            "3. Restart the application",
                            "See .env.example for reference",
                        ],
                    }
                ), 400

            # Check if API key exists in environment
            if not os.environ.get("OPENAI_API_KEY"):
                # Also check database for legacy keys (but warn about deprecation)
                if not SystemSettings.has_api_key("openai"):
                    return jsonify(
                        {
                            "error": "API key required for OpenAI provider",
                            "message": "Please set the OPENAI_API_KEY environment variable.",
                            "instructions": [
                                "1. Create or edit the .env file in the project root",
                                "2. Add: OPENAI_API_KEY=your_api_key_here",
                                "3. Restart the application",
                                "See .env.example for reference",
                            ],
                        }
                    ), 400
                else:
                    # Key exists in database but warn it's deprecated
                    import logging

                    logging.warning(
                        "OpenAI API key loaded from database. This is deprecated. Please set OPENAI_API_KEY environment variable."
                    )

        # Normalize OpenAI-compatible URLs so /v1 is optional
        if provider in ["openai-compatible", "lm-studio"] and ollama_url:
            ollama_url = _normalize_openai_compatible_url(ollama_url)

        # Validate URL for Ollama and OpenAI-Compatible providers
        if provider in ["ollama", "openai-compatible", "lm-studio"] and ollama_url:
            if not (
                ollama_url.startswith("http://") or ollama_url.startswith("https://")
            ):
                return jsonify(
                    {"error": "Server URL must start with http:// or https://"}
                ), 400

        # Save settings to database (provider, model, ollama_url only - not API keys)
        user_id = current_user.id if current_user.is_authenticated else None

        # Always update provider and model
        SystemSettings.set_llm_provider(provider, user_id=user_id)
        SystemSettings.set_llm_model(model, user_id=user_id)

        # Save provider-specific URL for each provider
        if provider in ["ollama", "openai-compatible", "lm-studio"] and ollama_url:
            SystemSettings.set_provider_url(provider, ollama_url, user_id=user_id)

        # Save context window for LM Studio
        if provider == "lm-studio" and context_window:
            try:
                context_window = int(context_window)
                if context_window > 0:
                    SystemSettings.set_setting(
                        "lm_studio_context_window", context_window, user_id=user_id
                    )
            except (ValueError, TypeError):
                pass  # Invalid context window, ignore

        # Update Flask config for current session
        from flask import current_app

        current_app.config["LLM_PROVIDER"] = provider
        current_app.config["LLM_MODEL"] = model
        if provider in ["ollama", "openai-compatible", "lm-studio"] and ollama_url:
            current_app.config["OLLAMA_URL"] = ollama_url

        return jsonify(
            {
                "message": "LLM settings updated successfully",
                "settings": {
                    "provider": provider,
                    "model": model,
                    "ollama_url": ollama_url
                    or SystemSettings.get_setting(
                        "ollama_url", "http://localhost:11434"
                    )
                    if provider in ["ollama", "openai-compatible", "lm-studio"]
                    else None,
                },
            }
        )


@admin.route("/test-ollama-connection", methods=["POST"])
@admin_required
def test_ollama_connection():
    """Test connection to Ollama server and fetch available models.

    Refactored to use helper functions for code deduplication.
    """
    import requests
    import os

    data = request.get_json()
    ollama_url = data.get("ollama_url", "http://localhost:11434").strip()
    api_key = data.get("api_key", "").strip()
    provider = data.get("provider", "ollama")
    is_openai_compat = provider in ["openai-compatible", "lm-studio"]

    # NEW-003: Validate URL with strict parsing to prevent SSRF attacks
    is_valid, error_msg = validate_llm_server_url(ollama_url)
    if not is_valid:
        return jsonify(
            {
                "success": False,
                "error": f"Invalid URL: {error_msg}",
            }
        ), 400

    # If API key is not provided in request, try to read from environment variables
    if not api_key:
        if is_openai_compat:
            api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY", "").strip()
        elif provider == "ollama":
            api_key = os.environ.get("OLLAMA_API_KEY", "").strip()

        # If still no API key in environment, try database (fallback for admin panel entries)
        if not api_key:
            from backend.models import SystemSettings

            if is_openai_compat:
                # OpenAI-compatible uses 'openai' key in database
                db_key = SystemSettings.get_api_key("openai")
                if db_key:
                    api_key = db_key.strip()
                    logger.info("Retrieved OpenAI-compatible API key from database")
            elif provider == "ollama":
                # Ollama uses 'ollama' key in database
                db_key = SystemSettings.get_api_key("ollama")
                if db_key:
                    api_key = db_key.strip()
                    logger.info("Retrieved Ollama API key from database")

    try:
        # Prepare headers (optional API key if provided)
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if is_openai_compat:
            ollama_url = _normalize_openai_compatible_url(ollama_url)

        # Determine primary and fallback endpoints based on provider
        # OpenAI-compatible uses /v1/models, Ollama native uses /api/tags
        if is_openai_compat:
            primary_endpoint = "/v1/models"
            fallback_endpoint = "/api/tags"
        else:  # provider == "ollama"
            primary_endpoint = "/api/tags"
            fallback_endpoint = "/v1/models"

        # Use helper function to try endpoints with fallback
        success, endpoint_type, response_json = _try_endpoint_with_fallback(
            ollama_url, primary_endpoint, fallback_endpoint, headers, timeout=10
        )

        # Handle authentication errors
        if not success and endpoint_type is None:
            # Check if it was an auth error (status 401/403)
            response = requests.get(
                f"{ollama_url}{primary_endpoint}", headers=headers, timeout=10
            )
            if response.status_code in (401, 403):
                return jsonify(
                    {
                        "success": False,
                        "error": f"Authentication failed (status {response.status_code}). "
                        f"Please verify your API key is correct for the {provider} provider. "
                        f"If using LocalLLM, the same key works for both Ollama and OpenAI-compatible modes.",
                    }
                ), 400

            # Connection failed
            return jsonify(
                {
                    "success": False,
                    "error": f"Server returned status {response.status_code} for both endpoints. "
                    f"Unable to connect as either OpenAI-compatible or Ollama server.",
                }
            ), 400

        # Success - fetch models using the appropriate helper
        if endpoint_type == "openai-compatible":
            models, loaded_models = _fetch_models_from_openai_compatible(
                ollama_url, headers, timeout=10
            )
            if models is None:
                # Should not happen since we already verified connection, but handle it
                models, loaded_models = [], []
        else:  # endpoint_type == "ollama-native"
            models, loaded_models = _fetch_models_from_ollama_native(
                ollama_url, headers, timeout=10
            )
            if models is None:
                models, loaded_models = [], []

        # Store the detected server type for later use during extraction
        from backend.models import SystemSettings

        SystemSettings.set_setting("ollama_server_type", endpoint_type)

        logger.info(
            f"Returning {len(models)} total models, {len(loaded_models)} loaded"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Successfully connected to server ({endpoint_type})",
                "models": models,
                "loaded_models": loaded_models,
                "model_count": len(models),
                "loaded_count": len(loaded_models),
                "server_type": endpoint_type,
            }
        )

    except requests.exceptions.Timeout:
        return jsonify(
            {
                "success": False,
                "error": "Connection timeout. Verify the server is running and accessible.",
            }
        ), 400
    except requests.exceptions.ConnectionError:
        return jsonify(
            {
                "success": False,
                "error": "Could not connect to the server. Verify the URL and that the server is running.",
            }
        ), 400
    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Connection test failed: {str(e)}"}
        ), 400


@admin.route("/save-api-key", methods=["POST"])
@admin_required
def save_api_key():
    """Save API key to .env file and reload environment."""
    import os
    import stat

    data = request.get_json()
    provider = data.get("provider", "openai")
    api_key = data.get("api_key", "").strip()

    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    # Validate provider
    valid_providers = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "cohere": "COHERE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "ollama": "OLLAMA_API_KEY",
        "openai-compatible": "OPENAI_COMPATIBLE_API_KEY",
        "lm-studio": "OPENAI_COMPATIBLE_API_KEY",
    }

    if provider not in valid_providers:
        return jsonify(
            {
                "error": f"Invalid provider. Valid providers: {list(valid_providers.keys())}"
            }
        ), 400

    env_var_name = valid_providers[provider]

    # Validate API key format - reject keys with invalid characters
    # This prevents issues with trailing quotes, newlines, or other special characters
    invalid_chars = ["\n", "\r", "\t", '"', "'", "\\"]
    if any(char in api_key for char in invalid_chars):
        return jsonify(
            {
                "error": "API key contains invalid characters. Please remove any quotes, newlines, or special characters."
            }
        ), 400

    # Get project root
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    env_file = os.path.join(project_root, ".env")

    try:
        # Read existing .env file or create new content
        existing_lines = []
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                existing_lines = f.readlines()

        # Update or add the API key line
        updated = False
        new_lines = []
        env_line = f"{env_var_name}={api_key}\n"

        for line in existing_lines:
            # Check if this line sets the same env var
            if line.strip().startswith(f"{env_var_name}="):
                # Replace existing line
                new_lines.append(env_line)
                updated = True
            else:
                new_lines.append(line)

        # If not found, append the new line
        if not updated:
            new_lines.append(env_line)

        # Write to .env file
        with open(env_file, "w") as f:
            f.writelines(new_lines)

        # Set secure permissions (read/write by owner only)
        os.chmod(env_file, stat.S_IRUSR | stat.S_IWUSR)

        # CRITICAL: Update the current process's environment immediately
        os.environ[env_var_name] = api_key

        # Update Flask config if this is the active provider
        from flask import current_app

        current_provider = current_app.config.get("LLM_PROVIDER")
        if current_provider == provider:
            current_app.config["LLM_API_KEY"] = api_key

        return jsonify(
            {
                "success": True,
                "message": f"API key saved and activated as {env_var_name}",
                "instructions": [
                    "The API key has been saved to .env file and activated immediately.",
                    "No restart required - you can start using it right away!",
                ],
                "env_var": env_var_name,
                "active": True,  # Indicate that the key is now active
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to save API key: {str(e)}"}), 500


@admin.route("/system-status")
@admin_required
def system_status():
    """Get system status and health information."""
    from datetime import datetime
    import os
    import sys

    # Database status
    try:
        # Simple query to test database connection
        db.session.query(User).first()
        db_status = "healthy"
        db_error = None
    except Exception as e:
        db_status = "error"
        db_error = str(e)

    # LLM service status
    llm_status = "unknown"
    llm_error = None
    provider = "unknown"
    model = "Not configured"

    try:
        from flask import current_app

        config = current_app.config
        from backend.services import LLMService
        from backend.models import SystemSettings
        import os

        # Check if API key is available (priority: environment variable > database)
        provider = config.get("LLM_PROVIDER", "openai")
        model = config.get("LLM_MODEL", "Not configured")
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "cohere": "COHERE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "ollama": "OLLAMA_API_KEY",
            "openai-compatible": "OPENAI_COMPATIBLE_API_KEY",
            "lm-studio": "OPENAI_COMPATIBLE_API_KEY",
        }

        env_var = env_var_map.get(provider)
        has_env_key = env_var and os.environ.get(env_var)

        if has_env_key:
            # API key loaded from environment (preferred method)
            llm_service = LLMService(config)
            # Test connection (for OpenAI)
            if llm_service.provider == "openai":
                llm_service.client.models.list()
            llm_status = "healthy"
        elif SystemSettings.has_api_key(provider):
            # Check database for legacy API key
            try:
                api_key = SystemSettings.get_api_key(provider)
                if api_key:
                    llm_service = LLMService(config)
                    # Test connection (for OpenAI)
                    if llm_service.provider == "openai":
                        llm_service.client.models.list()
                    llm_status = "healthy"
                else:
                    llm_status = "error"
                    llm_error = f"API key exists in database but cannot be decrypted. Please set the {provider.upper()} API key via LLM Settings to use environment variables (recommended)."
            except Exception as key_error:
                llm_status = "error"
                llm_error = f"API key decryption failed: {str(key_error)}. Please set the {provider.upper()} API key via LLM Settings to use environment variables (recommended)."
        else:
            llm_status = "error"
            env_label = env_var or f"{provider.upper()}_API_KEY"
            llm_error = f"API key not configured. Please set {env_label} environment variable or use LLM Settings."
    except Exception as e:
        llm_status = "error"
        llm_error = str(e)

    # Storage status
    storage_status = "unknown"
    try:
        import shutil

        total, used, free = shutil.disk_usage(".")
        storage_status = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "usage_percent": round((used / total) * 100, 2),
        }
    except Exception as e:
        storage_status = {"error": str(e)}

    # System info
    system_info = {
        "python_version": sys.version,
        "environment": os.environ.get("FLASK_ENV", "development"),
        "app_version": "1.0.0",
    }

    return jsonify(
        {
            "database": {"status": db_status, "error": db_error},
            "llm_service": {
                "status": llm_status,
                "error": llm_error,
                "provider": provider,
                "model": model,
            },
            "storage": storage_status,
            "system": system_info,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@admin.route("/users/<int:user_id>/limits", methods=["PUT"])
@admin_required
def update_user_limits(user_id):
    """Update user file limits."""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        # Prevent modifying admin users' limits (except by other admins)
        if user.is_admin and not current_user.is_admin:
            return jsonify({"error": "Cannot modify admin user limits"}), 403

        # Validate max_files_per_session
        max_files = data.get("max_files_per_session")
        if max_files is None:
            return jsonify({"error": "max_files_per_session is required"}), 400

        # Validate range
        if not isinstance(max_files, int) or max_files < 1 or max_files > 1000:
            return jsonify(
                {"error": "max_files_per_session must be between 1 and 1000"}
            ), 400

        # Update user limit
        user.max_files_per_session = max_files
        db.session.commit()

        return jsonify(
            {
                "message": f"Updated file limit for {user.email} to {max_files} files per session",
                "user_id": user.id,
                "email": user.email,
                "max_files_per_session": user.max_files_per_session,
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to update user limits: {str(e)}"}), 500


@admin.route("/db-health", methods=["GET"])
@admin_required
def get_database_health():
    """Get database connection pool health status."""
    from backend.utils.db_health import check_database_health, get_connection_pool_stats

    # Get overall health check
    health = check_database_health()

    # Get detailed pool statistics
    pool_stats = get_connection_pool_stats()

    return jsonify(
        {
            "health": health,
            "pool_details": pool_stats,
            "recommendations": _get_pool_recommendations(pool_stats),
        }
    )


def _get_pool_recommendations(pool_stats):
    """Get recommendations based on pool statistics."""
    recommendations = []

    if pool_stats.get("status") == "error":
        return recommendations

    usage = pool_stats.get("usage_percentage", 0)

    if usage > 90:
        recommendations.append(
            {
                "level": "critical",
                "message": "Connection pool is critically full. Consider increasing pool_size or max_overflow.",
                "action": 'Increase SQLALCHEMY_ENGINE_OPTIONS["pool_size"] in configuration',
            }
        )
    elif usage > 75:
        recommendations.append(
            {
                "level": "warning",
                "message": "Connection pool usage is high. Monitor for potential bottlenecks.",
                "action": "Consider increasing max_overflow or optimizing queries",
            }
        )
    elif usage < 20:
        recommendations.append(
            {
                "level": "info",
                "message": "Connection pool usage is low. Pool size may be oversized for current load.",
                "action": "Consider reducing pool_size to save resources",
            }
        )

    # Check for SQLite limitations
    pool_size = pool_stats.get("pool_size", 0)
    if pool_size > 10:
        recommendations.append(
            {
                "level": "info",
                "message": "SQLite has limitations with concurrent connections. Consider using PostgreSQL for production.",
                "action": "Set DATABASE_URL to PostgreSQL/MySQL for production use",
            }
        )

    return recommendations
