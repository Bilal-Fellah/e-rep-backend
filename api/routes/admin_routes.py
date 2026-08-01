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
from api.repositories.preapproved_mail_repository import PreapprovedMailRepository
from api.repositories.subscription_repository import SubscriptionRepository
from api.services.admin_service import AdminService
from api.services.subscription_service import SubscriptionService
from api.utils.datetime_utils import iso_utc
from api.utils.permissions import require_role

admin_bp = Blueprint("admin", __name__)

register_blueprint_error_handlers(admin_bp, include_integrity_handler=True)

ALLOWED_USER_ROLES = ("registered", "subscribed", "admin")


def _serialize_user(user):
    active_subscription = SubscriptionRepository.get_active_for_user(user.id)
    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "profession": user.profession,
        "phone_number": user.phone_number,
        "is_verified": bool(getattr(user, "is_verified", False)),
        "created_at": iso_utc(user.created_at),
        "subscription": {
            "pack_code": getattr(active_subscription, "pack_code", None),
            "status": getattr(active_subscription, "status", None),
            "starts_at": iso_utc(getattr(active_subscription, "starts_at", None)),
            "ends_at": iso_utc(getattr(active_subscription, "ends_at", None)),
            "access_rights": getattr(active_subscription, "access_rights", None),
        },
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
    """List users with optional search, role filter, and pagination.

    Query params: search (str), role (registered|subscribed|admin),
    limit (int, default 50, max 200), offset (int).
    """
    search = request.args.get("search")
    role = request.args.get("role")
    if role and role not in ALLOWED_USER_ROLES:
        return error_response(
            f"role must be one of {list(ALLOWED_USER_ROLES)}.", 400
        )
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    users = UserRepository.list_users(
        search=search, limit=limit, offset=offset, role=role
    )
    total = UserRepository.count_users(search=search, role=role)

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
    """Change a user's role (registered | admin).

    Note: The 'subscribed' role cannot be set directly. It is automatically
    derived from active paid subscriptions. Use /users/<id>/subscriptions/grant
    to grant a subscription pack, which will sync the user's role to 'subscribed'.
    """
    data = request.get_json() or {}
    role = data.get("role")
    if role not in ALLOWED_USER_ROLES:
        return error_response(
            f"role must be one of {list(ALLOWED_USER_ROLES)}.", 400
        )

    # Prevent direct changes to 'subscribed' role - it must come from an active subscription.
    if role == "subscribed":
        return error_response(
            "Cannot directly set role to 'subscribed'. "
            "Use /users/<id>/subscriptions/grant to grant a subscription pack, "
            "which will automatically set the user's role to 'subscribed'.",
            400,
        )

    # Guard against an admin removing their own admin access (self-lockout).
    if user_id == getattr(request, "user_id", None) and role != "admin":
        return error_response("You cannot change your own admin role.", 400)

    # Fetch the user first to check current state
    user = UserRepository.get_by_id(user_id)
    if not user:
        return error_response("User not found.", 404)

    # If downgrading from 'subscribed' to 'registered', sync with subscriptions first
    # to ensure the change is legitimate (no active paid subscription exists).
    if user.role == "subscribed" and role == "registered":
        # Sync role from current subscriptions - if user has active paid sub, role won't change
        synced_user, active = SubscriptionService._sync_user_role_from_subscriptions(user_id)
        if synced_user.role == "subscribed":
            return error_response(
                f"Cannot downgrade to 'registered': user has an active paid subscription "
                f"(pack: {active.pack_code}). Revoke or expire the subscription first.",
                400,
            )
        return success_response(_serialize_user(synced_user))

    # For admin<->registered transitions or setting registered on non-subscribed users
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


@admin_bp.route("/users/<int:user_id>/subscriptions", methods=["GET"])
@require_role("admin")
def list_user_subscriptions(user_id):
    """List a user's subscription history (newest first)."""
    user = UserRepository.get_by_id(user_id)
    if not user:
        return error_response("User not found.", 404)

    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    rows = SubscriptionRepository.list_for_user(user_id=user.id, limit=limit, offset=offset)
    data = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "status": row.status,
            "pack_code": row.pack_code,
            "access_rights": row.access_rights,
            "starts_at": iso_utc(row.starts_at),
            "ends_at": iso_utc(row.ends_at),
            "source": row.source,
            "preapproved_mail_id": row.preapproved_mail_id,
            "created_by_user_id": row.created_by_user_id,
            "created_at": iso_utc(row.created_at),
        }
        for row in rows
    ]
    return success_response({"subscriptions": data, "limit": limit, "offset": offset})


@admin_bp.route("/users/<int:user_id>/subscriptions/grant", methods=["POST"])
@require_role("admin")
def grant_subscription(user_id):
    """Grant a subscription pack for a specific user with an optional end date."""
    payload = request.get_json() or {}

    if not payload.get("pack_code"):
        return error_response("Missing required field: 'pack_code'.", 400)

    access_rights = payload.get("access_rights")
    if access_rights is not None and not isinstance(access_rights, dict):
        return error_response("'access_rights' must be an object.", 400)

    user = UserRepository.get_by_id(user_id)
    if not user:
        return error_response("User not found.", 404)

    try:
        created, synced_user, active = SubscriptionService.grant_subscription(
            user_id=user.id,
            pack_code=str(payload.get("pack_code")).strip(),
            starts_at=payload.get("starts_at"),
            ends_at=payload.get("ends_at"),
            access_rights=access_rights,
            source="admin",
            created_by_user_id=getattr(request, "user_id", None),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(
        {
            "subscription": {
                "id": created.id,
                "status": created.status,
                "pack_code": created.pack_code,
                "access_rights": created.access_rights,
                "starts_at": iso_utc(created.starts_at),
                "ends_at": iso_utc(created.ends_at),
                "source": created.source,
            },
            "active_subscription": {
                "pack_code": getattr(active, "pack_code", None),
                "status": getattr(active, "status", None),
                "starts_at": iso_utc(getattr(active, "starts_at", None)),
                "ends_at": iso_utc(getattr(active, "ends_at", None)),
                "access_rights": getattr(active, "access_rights", None),
            },
            "user": _serialize_user(synced_user),
        }
    )


@admin_bp.route("/users/<int:user_id>/subscriptions/<int:subscription_id>/revoke", methods=["POST"])
@require_role("admin")
def revoke_subscription(user_id, subscription_id):
    """Revoke a specific subscription and sync the user's role.

    After revocation, if the user has no other active paid subscriptions,
    their role will be downgraded to 'registered'.
    """
    # Verify the subscription belongs to this user
    sub = SubscriptionRepository.get_by_id(subscription_id)
    if not sub:
        return error_response("Subscription not found.", 404)
    if sub.user_id != user_id:
        return error_response("Subscription does not belong to this user.", 400)

    # Check if already in a terminal state
    if sub.status in ("revoked", "expired", "canceled"):
        return error_response(
            f"Subscription is already {sub.status} and cannot be revoked.",
            400
        )

    try:
        revoked, synced_user, active = SubscriptionService.revoke_subscription(subscription_id)
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(
        {
            "subscription": {
                "id": revoked.id,
                "status": revoked.status,
                "pack_code": revoked.pack_code,
                "access_rights": revoked.access_rights,
                "starts_at": iso_utc(revoked.starts_at),
                "ends_at": iso_utc(revoked.ends_at),
                "source": revoked.source,
            },
            "active_subscription": {
                "pack_code": getattr(active, "pack_code", None),
                "status": getattr(active, "status", None),
                "starts_at": iso_utc(getattr(active, "starts_at", None)),
                "ends_at": iso_utc(getattr(active, "ends_at", None)),
                "access_rights": getattr(active, "access_rights", None),
            } if active else None,
            "user": _serialize_user(synced_user),
        }
    )


@admin_bp.route("/preapproved-mails", methods=["GET"])
@require_role("admin")
def list_preapproved_mails():
    """List preapproved emails and their pending/used/revoked status."""
    email = request.args.get("email")
    status = request.args.get("status")
    allowed_statuses = {"pending", "used", "revoked", "expired"}
    if status and status not in allowed_statuses:
        return error_response(f"status must be one of {sorted(allowed_statuses)}.", 400)

    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    rows = PreapprovedMailRepository.list_items(
        email=email,
        status=status,
        limit=limit,
        offset=offset,
    )
    total = PreapprovedMailRepository.count_items(email=email, status=status)

    data = [
        {
            "id": row.id,
            "email": row.email,
            "status": row.status,
            "pack_code": row.pack_code,
            "access_rights": row.access_rights,
            "starts_at": iso_utc(row.starts_at),
            "ends_at": iso_utc(row.ends_at),
            "created_by_user_id": row.created_by_user_id,
            "notes": row.notes,
            "created_at": iso_utc(row.created_at),
            "updated_at": iso_utc(row.updated_at),
            "used_at": iso_utc(row.used_at),
        }
        for row in rows
    ]

    return success_response(
        {
            "items": data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@admin_bp.route("/preapproved-mails/upsert", methods=["POST"])
@require_role("admin")
def upsert_preapproved_mail():
    """Create/update a preapproved email that auto-applies on signup."""
    payload = request.get_json() or {}

    email = payload.get("email")
    pack_code = payload.get("pack_code")
    if not email:
        return error_response("Missing required field: 'email'.", 400)
    if not pack_code:
        return error_response("Missing required field: 'pack_code'.", 400)

    access_rights = payload.get("access_rights")
    if access_rights is not None and not isinstance(access_rights, dict):
        return error_response("'access_rights' must be an object.", 400)

    try:
        row = SubscriptionService.upsert_preapproved_mail(
            email=email,
            pack_code=pack_code,
            starts_at=payload.get("starts_at"),
            ends_at=payload.get("ends_at"),
            access_rights=access_rights,
            notes=payload.get("notes"),
            created_by_user_id=getattr(request, "user_id", None),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)

    return success_response(
        {
            "id": row.id,
            "email": row.email,
            "status": row.status,
            "pack_code": row.pack_code,
            "access_rights": row.access_rights,
            "starts_at": iso_utc(row.starts_at),
            "ends_at": iso_utc(row.ends_at),
            "notes": row.notes,
            "created_by_user_id": row.created_by_user_id,
            "created_at": iso_utc(row.created_at),
            "updated_at": iso_utc(row.updated_at),
        }
    )


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


@admin_bp.route("/health", methods=["GET"])
@require_role("admin")
def get_health():
    """System health: DB reachability, scrape freshness, recent error count."""
    return success_response(AdminService.get_health())


@admin_bp.route("/alerts", methods=["GET"])
@require_role("admin")
def get_alerts():
    """Aggregated operational alerts across scraping, accounts, data, and errors."""
    return success_response(AdminService.get_alerts())
