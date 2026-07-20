# routes/admin_routes.py
#
# Admin-only endpoints backing the standalone Brendex Admin dashboard.
# Everything here is gated to the "admin" role via @require_role and the
# ROLE_PERMISSIONS matrix in api/utils/permissions.py. Follows the standard
# routes -> services -> repositories layering used across the API.
from flask import Blueprint, request

from api.routes.main import (
    error_response,
    success_response,
    register_blueprint_error_handlers,
)
from api.repositories.user_repository import UserRepository
from api.services.admin_service import AdminService
from api.utils.permissions import require_role

admin_bp = Blueprint("admin", __name__)

register_blueprint_error_handlers(admin_bp, include_integrity_handler=True)

ALLOWED_USER_ROLES = ("registered", "subscribed", "admin")


def _serialize_user(user):
    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "profession": user.profession,
        "phone_number": user.phone_number,
        "is_verified": bool(getattr(user, "is_verified", False)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@admin_bp.route("/ping", methods=["GET"])
@require_role("admin")
def ping():
    """Lightweight wiring/auth check for the admin dashboard.

    Returns the caller's identity so the frontend guard can confirm the
    session is a genuine admin before rendering the dashboard shell.
    """
    return success_response(
        {
            "ok": True,
            "user_id": getattr(request, "user_id", None),
            "role": getattr(request, "user_role", None),
        }
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@admin_bp.route("/users", methods=["GET"])
@require_role("admin")
def list_users():
    """List users with optional search and pagination.

    Query params: search (str), limit (int, default 50, max 200), offset (int).
    """
    search = request.args.get("search")
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    users = UserRepository.list_users(search=search, limit=limit, offset=offset)
    total = UserRepository.count_users(search=search)

    return success_response(
        {
            "users": [_serialize_user(u) for u in users],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@require_role("admin")
def set_user_role(user_id):
    """Change a user's role (registered | subscribed | admin)."""
    data = request.get_json() or {}
    role = data.get("role")
    if role not in ALLOWED_USER_ROLES:
        return error_response(
            f"role must be one of {list(ALLOWED_USER_ROLES)}.", 400
        )

    # Guard against an admin removing their own admin access (self-lockout).
    if user_id == getattr(request, "user_id", None) and role != "admin":
        return error_response("You cannot change your own admin role.", 400)

    # Change only the role — leave is_verified alone (activation is a separate
    # admin action). update_profile raises ValueError when the user doesn't
    # exist; catch it for a 404 rather than a redundant pre-fetch or generic 400.
    try:
        updated = UserRepository.update_profile(user_id, role=role)
    except ValueError:
        return error_response("User not found.", 404)
    return success_response(_serialize_user(updated))


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@require_role("admin")
def activate_user(user_id):
    """Set a user's account activation flag (is_verified)."""
    data = request.get_json() or {}
    is_verified = data.get("is_verified")
    if is_verified is None:
        return error_response("Missing required field: 'is_verified'.", 400)
    if not isinstance(is_verified, bool):
        return error_response("'is_verified' must be a boolean.", 400)

    # update_profile raises ValueError when the user doesn't exist; catch it so a
    # missing user is a 404 rather than a second lookup or a generic 400.
    try:
        updated = UserRepository.update_profile(
            user_id, is_verified=bool(is_verified)
        )
    except ValueError:
        return error_response("User not found.", 404)
    return success_response(_serialize_user(updated))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_role("admin")
def delete_user(user_id):
    """Permanently delete a user account."""
    # Never let an admin delete their own account out from under themselves.
    if user_id == getattr(request, "user_id", None):
        return error_response("You cannot delete your own account.", 400)

    deleted = UserRepository.delete(user_id)
    if not deleted:
        return error_response("User not found.", 404)

    return success_response({"deleted_id": user_id})


# ---------------------------------------------------------------------------
# Logs & alerts
# ---------------------------------------------------------------------------

@admin_bp.route("/logs", methods=["GET"])
@require_role("admin")
def get_logs():
    """Read the backend JSONL error logs (newest first).

    Query params:
        source   - route | service | repository | all (default all)
        severity - low | medium | high (optional)
        period   - YYYY-MM (default current month)
        limit    - default 100, max 500
        offset   - default 0
    """
    source = request.args.get("source")
    severity = request.args.get("severity")
    period = request.args.get("period")
    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)

    result = AdminService.get_logs(
        source=source,
        severity=severity,
        period=period,
        limit=limit,
        offset=offset,
    )
    return success_response(result)


@admin_bp.route("/overview", methods=["GET"])
@require_role("admin")
def get_overview():
    """Aggregate counts for the dashboard landing (entities, pages, users)."""
    return success_response(AdminService.get_overview())


@admin_bp.route("/alerts", methods=["GET"])
@require_role("admin")
def get_alerts():
    """Aggregated operational alerts across scraping, accounts, data, and errors."""
    return success_response(AdminService.get_alerts())
