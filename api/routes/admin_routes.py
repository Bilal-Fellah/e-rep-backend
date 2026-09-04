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
from api.services.correction_service import CorrectionError, CorrectionService
from api.services.data_integrity_service import DataIntegrityService
from api.services.orchestration_report_service import OrchestrationReportService
from api.services.priority_entity_service import PriorityEntityError, PriorityEntityService
from api.services.scraper_credential_service import ScraperCredentialError, ScraperCredentialService
from api.services.scrape_trigger_service import ScrapeTriggerError, ScrapeTriggerService
from api.services.scraping_health_service import ScrapingHealthService
from api.services.tracked_keyword_service import TrackedKeywordService
from api.services.subscription_service import SubscriptionService
from api.services.posts_created_at_service import PostsCreatedAtService
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


@admin_bp.route("/subscriptions", methods=["GET"])
@require_role("admin")
def list_all_subscriptions():
    """List all subscriptions with optional filters (admin only)."""
    status = request.args.get("status")
    pack_code = request.args.get("pack_code")
    source = request.args.get("source")

    allowed_statuses = {"pending", "active", "expired", "canceled", "revoked"}
    if status and status not in allowed_statuses:
        return error_response(f"status must be one of {sorted(allowed_statuses)}.", 400)

    allowed_packs = {"starter", "growth", "advanced"}
    if pack_code and pack_code not in allowed_packs:
        return error_response(f"pack_code must be one of {sorted(allowed_packs)}.", 400)

    allowed_sources = {"admin", "preapproved_mail", "stripe", "manual"}
    if source and source not in allowed_sources:
        return error_response(f"source must be one of {sorted(allowed_sources)}.", 400)

    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    rows = SubscriptionRepository.list_all_with_user_email(
        status=status,
        pack_code=pack_code,
        source=source,
        limit=limit,
        offset=offset,
    )
    total = SubscriptionRepository.count_all(
        status=status,
        pack_code=pack_code,
        source=source,
    )

    data = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "user_email": email,
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
        for row, email in rows
    ]

    return success_response(
        {
            "subscriptions": data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


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


@admin_bp.route("/corrections/targets", methods=["GET"])
@require_role("admin")
def get_correction_targets():
    """Whitelist of what can be corrected, for the admin UI to render a form from."""
    return success_response({"targets": CorrectionService.list_targets()})


@admin_bp.route("/corrections", methods=["GET"])
@require_role("admin")
def list_corrections():
    """History of applied corrections, newest first."""
    target_type = request.args.get("target_type") or None
    valid_target_types = CorrectionService.valid_target_types()
    if target_type and target_type not in valid_target_types:
        return error_response(f"target_type must be one of {valid_target_types}.", 400)

    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except ValueError:
        return error_response("limit must be an integer.", 400)
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return error_response("offset must be an integer.", 400)

    rows, total = CorrectionService.list_corrections(target_type=target_type, limit=limit, offset=offset)
    return success_response(
        {
            "corrections": [
                {
                    "id": row.id,
                    "admin_user_id": row.admin_user_id,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "field": row.field,
                    "old_value": row.old_value,
                    "new_value": row.new_value,
                    "reason": row.reason,
                    "created_at": iso_utc(row.created_at),
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@admin_bp.route("/corrections", methods=["POST"])
@require_role("admin")
def create_correction():
    """Apply a whitelisted correction to one row/field and log it to the
    data_corrections audit trail in the same transaction."""
    payload = request.get_json() or {}

    target_type = payload.get("target_type")
    target_id = payload.get("target_id")
    field = payload.get("field")
    reason = payload.get("reason")

    if not target_type:
        return error_response("Missing required field: 'target_type'.", 400)
    if target_id in (None, ""):
        return error_response("Missing required field: 'target_id'.", 400)
    if not field:
        return error_response("Missing required field: 'field'.", 400)
    if "new_value" not in payload:
        return error_response("Missing required field: 'new_value'.", 400)
    if not reason:
        return error_response("Missing required field: 'reason'.", 400)

    try:
        audit, _row = CorrectionService.apply_correction(
            target_type=target_type,
            target_id=target_id,
            field=field,
            new_value=payload.get("new_value"),
            reason=reason,
            admin_user_id=getattr(request, "user_id", None),
        )
    except CorrectionError as exc:
        return error_response(str(exc), 400)

    return success_response(
        {
            "id": audit.id,
            "target_type": audit.target_type,
            "target_id": audit.target_id,
            "field": audit.field,
            "old_value": audit.old_value,
            "new_value": audit.new_value,
            "reason": audit.reason,
            "created_at": iso_utc(audit.created_at),
        }
    )


@admin_bp.route("/data-integrity/summary", methods=["GET"])
@require_role("admin")
def get_data_integrity_summary():
    """Per-platform null-rate snapshot for profile fields (followers) and
    post metrics (likes/comments/shares), plus a few ready-to-correct
    sample rows. Read-only — see /corrections to actually fix a gap."""
    return success_response(DataIntegrityService.get_summary())


@admin_bp.route("/data-integrity/daily", methods=["GET"])
@require_role("admin")
def get_data_integrity_daily():
    """Same null rates as /summary, broken down by day so a bad scrape run
    on a specific date is visible instead of averaged away."""
    try:
        days = int(request.args.get("days", 14))
    except ValueError:
        return error_response("days must be an integer.", 400)
    return success_response(DataIntegrityService.get_daily(days=days))


@admin_bp.route("/data-integrity/validation-failures", methods=["GET"])
@require_role("admin")
def get_data_integrity_validation_failures():
    """Live output of the validation engine (PageHistoryRepository.
    validate_data_structure) — which pages' most recent scrape (since
    yesterday 10pm UTC) came back missing data, and what's missing.

    This is the same check GET /api/scraping/apify_profile_scraping uses,
    surfaced here so a human can see it directly rather than only through
    whatever automated consumer acts on it. Purely informational — looking
    at this triggers nothing downstream."""
    platform = request.args.get("platform")
    valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
    if platform and platform not in valid_platforms:
        return error_response(f"platform must be one of {valid_platforms}.", 400)
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return error_response("limit must be an integer.", 400)
    return success_response(
        DataIntegrityService.get_validation_failures(platform=platform, limit=limit)
    )


@admin_bp.route("/orchestration/summary", methods=["GET"])
@require_role("admin")
def get_orchestration_summary():
    """Success/partial/failed rate and fallback cost per platform+domain
    over the trailing window, from the scrape_attempts audit log written
    by ScrapeOrchestratorService. This is the "is our paid data actually
    available today" number — see api/docs/orchestration.md."""
    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        return error_response("days must be an integer.", 400)
    platform = request.args.get("platform")
    domain = request.args.get("domain")
    if domain and domain not in ("profile", "posts"):
        return error_response("domain must be 'profile' or 'posts'.", 400)
    return success_response(OrchestrationReportService.get_summary(days=days, platform=platform, domain=domain))


@admin_bp.route("/orchestration/daily", methods=["GET"])
@require_role("admin")
def get_orchestration_daily():
    """Same success/partial/failed counts as /summary, broken down by day."""
    try:
        days = int(request.args.get("days", 14))
    except ValueError:
        return error_response("days must be an integer.", 400)
    platform = request.args.get("platform")
    domain = request.args.get("domain")
    if domain and domain not in ("profile", "posts"):
        return error_response("domain must be 'profile' or 'posts'.", 400)
    return success_response(OrchestrationReportService.get_daily(days=days, platform=platform, domain=domain))


@admin_bp.route("/orchestration/attempts", methods=["GET"])
@require_role("admin")
def get_orchestration_attempts():
    """Recent individual scrape attempts, newest first — for drilling into
    *why* a platform's success rate dropped (which source failed, which
    fields it was missing, whether a fallback recovered it)."""
    platform = request.args.get("platform")
    domain = request.args.get("domain")
    final_status = request.args.get("status")
    if final_status and final_status not in ("complete", "partial", "failed"):
        return error_response("status must be one of 'complete', 'partial', 'failed'.", 400)
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return error_response("limit must be an integer.", 400)
    limit = max(1, min(limit, 200))
    return success_response(
        OrchestrationReportService.list_recent_attempts(
            platform=platform, domain=domain, final_status=final_status, limit=limit
        )
    )


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


# ---------------------------------------------------------------------------
# Posts created_at filling (read-only statistics)
# ---------------------------------------------------------------------------

@admin_bp.route("/posts/created-at/stats", methods=["GET"])
@require_role("admin")
def get_posts_created_at_stats():
    """
    Get statistics about posts with missing created_at values.
    
    Note: The system fills missing dates in-memory when posts are retrieved.
    This does not modify the database - it only enriches the response data.
    """
    stats = PostsCreatedAtService.get_missing_dates_stats()
    return success_response(stats)


# ---------------------------------------------------------------------------
# Scraper credentials (session cookies for platforms that require login --
# LinkedIn today). Values are never returned through these routes, only
# status/expiry -- see ScraperCredentialService for the masking and the
# api-key-gated routes in scraping_routes.py that the VPS scraper itself
# uses to fetch/report against the real value.
# ---------------------------------------------------------------------------

@admin_bp.route("/scraper-credentials", methods=["GET"])
@require_role("admin")
def list_scraper_credentials():
    """One row per platform: cookie count, expiry state, and the last real
    usage outcome reported by the scraper -- never the raw values."""
    return success_response({"credentials": ScraperCredentialService.list_masked()})


@admin_bp.route("/scraper-credentials", methods=["POST"])
@require_role("admin")
def upsert_scraper_credentials():
    """Paste a freshly-exported cookie jar for a platform. Full replace,
    not a merge -- see ScraperCredentialRepository.upsert."""
    payload = request.get_json() or {}

    platform = payload.get("platform")
    value = payload.get("value")
    credential_type = payload.get("credential_type", "cookies")

    if not platform:
        return error_response("Missing required field: 'platform'.", 400)
    if value is None:
        return error_response("Missing required field: 'value'.", 400)

    try:
        result = ScraperCredentialService.upsert_and_maybe_trigger(
            platform=platform,
            value=value,
            credential_type=credential_type,
            updated_by=getattr(request, "user_id", None),
        )
    except ScraperCredentialError as exc:
        return error_response(str(exc), 400)

    return success_response(result, 201)


# ---------------------------------------------------------------------------
# Manual scrape triggers -- fire an own-scraper run (profile/comments) from
# Brendex Admin without waiting for the next scheduled systemd timer. Just
# queues a "pending" row; a poller on the VPS claims and runs it via the
# api-key-gated routes in scraping_routes.py. See
# api/models/scrape_trigger_request_model.py and ScrapeTriggerService for
# exactly what's triggerable (own-scraper only -- not Bright Data/Apify).
# ---------------------------------------------------------------------------

@admin_bp.route("/scraping/trigger", methods=["POST"])
@require_role("admin")
def trigger_scrape():
    """Queue a manual scrape run. Picked up by the VPS watcher within
    ~30s; poll GET below for status."""
    payload = request.get_json() or {}

    platform = payload.get("platform")
    mode = payload.get("mode")

    if not platform:
        return error_response("Missing required field: 'platform'.", 400)
    if not mode:
        return error_response("Missing required field: 'mode'.", 400)

    try:
        result = ScrapeTriggerService.request_trigger(
            platform=platform,
            mode=mode,
            requested_by=getattr(request, "user_id", None),
        )
    except ScrapeTriggerError as exc:
        return error_response(str(exc), 400)

    return success_response(result, 201)


@admin_bp.route("/scraping/trigger", methods=["GET"])
@require_role("admin")
def list_scrape_triggers():
    """Recent manual-trigger history and status, newest first."""
    limit = request.args.get("limit", default=50, type=int)
    return success_response({"triggers": ScrapeTriggerService.list_recent(limit)})


# ---------------------------------------------------------------------------
# Client-owned TikTok keyword watchlist -- read-only here for support/
# debugging. Clients manage their own keywords via /api/data/keywords
# (JWT-gated, routes/data/keywords.py); this just lets an admin see who's
# tracking what and how many mentions each keyword has found so far.
# ---------------------------------------------------------------------------

@admin_bp.route("/keywords", methods=["GET"])
@require_role("admin")
def list_tracked_keywords():
    """Every client-tracked keyword for `platform` (default tiktok), across
    all users, with a mention count each."""
    platform = request.args.get("platform", default="tiktok")
    return success_response({"keywords": TrackedKeywordService.list_all_for_admin(platform)})


# ---------------------------------------------------------------------------
# Priority clients -- the short list of paying customers whose data gets
# checked harder than the fleet-wide Data Integrity report checks anything.
# Per-page freshness/completeness for one client, plus firing an
# own-scraper run on their behalf and verifying it actually produced data
# for *their* pages. See api/services/priority_entity_service.py for why a
# "run for this client" is still a platform-wide run under the hood, and
# api/docs/priority_entities.md for the response shapes.
# ---------------------------------------------------------------------------

@admin_bp.route("/priority/entities", methods=["GET"])
@require_role("admin")
def list_priority_entities():
    """Every priority client with its data health rolled up."""
    days = request.args.get("days", default=7, type=int)
    return success_response({"entities": PriorityEntityService.list_with_health(days)})


@admin_bp.route("/priority/entities", methods=["POST"])
@require_role("admin")
def add_priority_entity():
    """Put an entity on the priority list."""
    payload = request.get_json() or {}

    entity_id = payload.get("entity_id")
    if entity_id is None:
        return error_response("Missing required field: 'entity_id'.", 400)

    try:
        result = PriorityEntityService.add(
            entity_id=int(entity_id),
            label=payload.get("label"),
            note=payload.get("note"),
            added_by=getattr(request, "user_id", None),
        )
    except (TypeError, ValueError) as exc:
        # PriorityEntityError subclasses ValueError; a non-integer
        # entity_id lands here too, and both are the caller's mistake.
        return error_response(str(exc), 400)

    return success_response(result, 201)


@admin_bp.route("/priority/entities/<int:entity_id>", methods=["POST"])
@require_role("admin")
def update_priority_entity(entity_id):
    """Edit the label/note on a priority entry. An empty string clears the
    field; omitting it leaves it unchanged."""
    payload = request.get_json() or {}
    try:
        result = PriorityEntityService.update(
            entity_id=entity_id, label=payload.get("label"), note=payload.get("note")
        )
    except PriorityEntityError as exc:
        return error_response(str(exc), 400)
    return success_response(result)


@admin_bp.route("/priority/entities/<int:entity_id>", methods=["DELETE"])
@require_role("admin")
def remove_priority_entity(entity_id):
    """Take an entity off the priority list. Deletes nothing else."""
    try:
        result = PriorityEntityService.remove(entity_id)
    except PriorityEntityError as exc:
        return error_response(str(exc), 404)
    return success_response(result)


@admin_bp.route("/priority/entities/<int:entity_id>/check", methods=["GET"])
@require_role("admin")
def check_priority_entity(entity_id):
    """The full per-page validity report for one client."""
    days = request.args.get("days", default=7, type=int)
    try:
        result = PriorityEntityService.check_entity(entity_id, days)
    except PriorityEntityError as exc:
        return error_response(str(exc), 404)
    return success_response(result)


@admin_bp.route("/priority/entities/<int:entity_id>/scrape", methods=["POST"])
@require_role("admin")
def trigger_priority_scrape(entity_id):
    """Queue an own-scraper run on this client's behalf. Platform-wide
    under the hood -- tagged with the entity so the run can be attributed
    and then verified against this client's own pages."""
    payload = request.get_json() or {}

    platform = payload.get("platform")
    mode = payload.get("mode")
    if not platform:
        return error_response("Missing required field: 'platform'.", 400)
    if not mode:
        return error_response("Missing required field: 'mode'.", 400)

    try:
        result = PriorityEntityService.trigger_scrape(
            entity_id=entity_id,
            platform=platform,
            mode=mode,
            requested_by=getattr(request, "user_id", None),
        )
    except PriorityEntityError as exc:
        return error_response(str(exc), 400)

    return success_response(result, 201)


@admin_bp.route("/priority/entities/<int:entity_id>/scrape-check", methods=["GET"])
@require_role("admin")
def verify_priority_scrape(entity_id):
    """Did the run queued as `trigger_id` actually bring back data for this
    client's pages? Answered from the data itself, not the run's status."""
    trigger_id = request.args.get("trigger_id", type=int)
    if trigger_id is None:
        return error_response("Missing required query parameter: 'trigger_id'.", 400)

    try:
        result = PriorityEntityService.verify_scrape(entity_id, trigger_id)
    except PriorityEntityError as exc:
        return error_response(str(exc), 400)
    return success_response(result)


# ---------------------------------------------------------------------------
# Scraping Health -- per-day delivery for each collection source, and comment
# coverage measured against Bright Data's own per-post count. Distinct from
# /scraping (session-level operations): this asks what the data looks like
# once it lands, and whether anything is missing from it. See
# api/services/scraping_health_service.py and api/docs/scraping_health.md.
# ---------------------------------------------------------------------------

@admin_bp.route("/scraping-health/daily", methods=["GET"])
@require_role("admin")
def get_scraping_health_daily():
    """Per-day, per-platform activity for Bright Data and the own scraper,
    plus session outcomes. Query: days (default 14, max 90)."""
    days = request.args.get("days", default=14, type=int)
    return success_response(ScrapingHealthService.daily(days))


@admin_bp.route("/scraping-health/comment-coverage", methods=["GET"])
@require_role("admin")
def get_scraping_health_comment_coverage():
    """Are we collecting every comment that exists? Reach (did we visit the
    post) and completeness (did we get all of its comments) reported
    separately. Query: days -- the post-age window (default 30)."""
    days = request.args.get("days", default=30, type=int)
    return success_response(ScrapingHealthService.comment_coverage(days))
