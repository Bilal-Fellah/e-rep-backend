# Centralized Role-Based Access Control (RBAC) Configuration
# Single source of truth for all role-based permissions in the application

from enum import Enum
from functools import wraps
from flask import request
import jwt
import os
from api.utils.auth import _extract_token

SECRET = os.environ.get("SECRET_KEY")

# ============================================================================
# ROLE DEFINITIONS
# ============================================================================

class UserRole(Enum):
    """All available user roles in the system"""
    REGISTERED = "registered"
    SUBSCRIBED = "subscribed"
    ADMIN = "admin"

# Publicly accessible (no auth required)
PUBLIC = "public"

# ============================================================================
# ENDPOINT ACCESS CONTROL MATRIX
# This is the source of truth for what each role can access
# ============================================================================

ROLE_PERMISSIONS = {
    # PUBLIC ENDPOINTS (no authentication required)
    "public.public_ranking": [PUBLIC],
    "health.health": [PUBLIC],

    # AUTH ENDPOINTS (typically open to all)
    "auth.register_mail": [PUBLIC],
    "auth.register_user": [PUBLIC],
    "auth.register_entity_name": [PUBLIC],
    "auth.login": [PUBLIC],
    "auth.logout": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "auth.get_user_data": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "auth.refresh_token": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "auth.validate_user_role": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "auth.complete_profile": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "auth.redirect_to_app": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # ENTITY ENDPOINTS
    "data.add_entity": [UserRole.ADMIN.value],
    "data.get_all_entities": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_data_existing_entities": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.delete_entity": [UserRole.ADMIN.value],
    "data.get_entity_profile_card": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_entity_followers_history": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.compare_entities_followers": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_entity_likes_history": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.compare_entities_likes": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_entity_comments_history": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.compare_entities_comments": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_entity_posts_timeline": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.mark_entity_to_scrape": [UserRole.ADMIN.value],
    "data.get_entity_top_posts": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # PAGE ENDPOINTS
    "data.add_page": [UserRole.ADMIN.value],
    "data.delete_page": [UserRole.ADMIN.value],
    "data.get_all_pages": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_pages_by_platform": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_page_interaction_stats": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_pages_history": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_pages_history_by_id": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_pages_history_options": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_pages_history_summary": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # CATEGORY ENDPOINTS
    "data.get_all_categories": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # NOTE ENDPOINTS
    "data.create_note": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_note": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_notes_for_target": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_notes_by_author": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # SCRAPING STATUS ENDPOINTS (admin only)
    "scraping.get_scraping_summary": [UserRole.ADMIN.value],
    "scraping.get_scraping_sessions": [UserRole.ADMIN.value],
    "scraping.get_today_posts_status": [UserRole.ADMIN.value],

    # ADMIN DASHBOARD ENDPOINTS (admin only) — Brendex Admin standalone app
    "admin.ping": [UserRole.ADMIN.value],
    "admin.list_users": [UserRole.ADMIN.value],
    "admin.set_user_role": [UserRole.ADMIN.value],
    "admin.activate_user": [UserRole.ADMIN.value],
    "admin.delete_user": [UserRole.ADMIN.value],
    "admin.get_logs": [UserRole.ADMIN.value],
    "admin.get_alerts": [UserRole.ADMIN.value],
    "admin.get_overview": [UserRole.ADMIN.value],
    "admin.get_health": [UserRole.ADMIN.value],
    "admin.list_user_subscriptions": [UserRole.ADMIN.value],
    "admin.grant_subscription": [UserRole.ADMIN.value],
    "admin.list_preapproved_mails": [UserRole.ADMIN.value],
    "admin.upsert_preapproved_mail": [UserRole.ADMIN.value],
    "admin.get_correction_targets": [UserRole.ADMIN.value],
    "admin.list_corrections": [UserRole.ADMIN.value],
    "admin.create_correction": [UserRole.ADMIN.value],
    "admin.get_data_integrity_summary": [UserRole.ADMIN.value],
    "admin.get_data_integrity_daily": [UserRole.ADMIN.value],

    # Priority clients (paying customers watched more closely)
    "admin.list_priority_entities": [UserRole.ADMIN.value],
    "admin.add_priority_entity": [UserRole.ADMIN.value],
    "admin.update_priority_entity": [UserRole.ADMIN.value],
    "admin.remove_priority_entity": [UserRole.ADMIN.value],
    "admin.check_priority_entity": [UserRole.ADMIN.value],
    "admin.trigger_priority_scrape": [UserRole.ADMIN.value],
    "admin.verify_priority_scrape": [UserRole.ADMIN.value],

    # Entity admin extras (in the data blueprint)
    "data.update_entity": [UserRole.ADMIN.value],
    "data.set_entity_scrape": [UserRole.ADMIN.value],
    "data.add_category": [UserRole.ADMIN.value],
    "data.delete_category": [UserRole.ADMIN.value],
    "data.update_category": [UserRole.ADMIN.value],

    # Alerts (user-facing)
    "data.list_alerts": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.unread_alert_count": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.mark_alert_read": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.dismiss_alert": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.mark_all_alerts_read": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.list_alert_rules": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.create_alert_rule": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.update_alert_rule": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.delete_alert_rule": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],

    # Tracked keywords / mentions (user-facing)
    "data.list_keywords": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.create_keyword": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.delete_keyword": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.list_keyword_mentions": [UserRole.REGISTERED.value, UserRole.SUBSCRIBED.value, UserRole.ADMIN.value],
    "data.get_keyword_search_now_status": [UserRole.ADMIN.value],
    "data.trigger_keyword_search_now": [UserRole.ADMIN.value],
}

# ============================================================================
# TIME-BASED DATA RESTRICTIONS
# Registered users get limited view (last month), subscribed get full access
# ============================================================================

DATA_VISIBILITY_RULES = {
    # These endpoints have different data returned based on role
    "follower_history": {
        UserRole.REGISTERED.value: "last_month",  # Only last 30 days
        UserRole.SUBSCRIBED.value: "full",  # All data
        UserRole.ADMIN.value: "full",
    },
    "interaction_history": {
        UserRole.REGISTERED.value: "last_month",  # Only last 30 days
        UserRole.SUBSCRIBED.value: "full",  # All data
        UserRole.ADMIN.value: "full",
    },
    "top_posts": {
        UserRole.REGISTERED.value: "last_month",  # Only last 30 days
        UserRole.SUBSCRIBED.value: "full",  # All data
        UserRole.ADMIN.value: "full",
    },
    "brand_rankings": {
        UserRole.REGISTERED.value: "top_10_only",  # Only top 10 global
        UserRole.SUBSCRIBED.value: "full",  # All rankings
        UserRole.ADMIN.value: "full",
    },
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_data_visibility_for_role(endpoint_key: str, role: str) -> str:
    """
    Get the data visibility level for a specific role on an endpoint.

    Args:
        endpoint_key: Key in DATA_VISIBILITY_RULES
        role: User role

    Returns:
        Visibility level (e.g., "last_month", "full", "top_10_only")
    """
    if endpoint_key not in DATA_VISIBILITY_RULES:
        return "full"  # Default to full access if not restricted

    rules = DATA_VISIBILITY_RULES[endpoint_key]
    return rules.get(role, "full")


def can_user_access_endpoint(role: str, endpoint_blueprint: str, endpoint_name: str) -> bool:
    """
    Check if a user with given role can access a specific endpoint.

    Args:
        role: User role (from JWT)
        endpoint_blueprint: Blueprint name (e.g., "data", "auth")
        endpoint_name: Function name (e.g., "get_all_entities")

    Returns:
        True if user can access, False otherwise
    """
    endpoint_key = f"{endpoint_blueprint}.{endpoint_name}"
    allowed_roles = ROLE_PERMISSIONS.get(endpoint_key, [])

    # If endpoint is public, allow access
    if PUBLIC in allowed_roles:
        return True

    # Otherwise, check if user's role is in allowed roles
    return role in allowed_roles


def extract_and_validate_token():
    """
    Extract JWT token from request (Bearer header or cookie).

    Returns:
        tuple: (payload_dict, error_response) or (None, error_response) if invalid
    """
    try:
        token = _extract_token("access_token")
        if not token:
            return None, ("No valid token provided", 401)

        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ("Token has expired", 401)
    except jwt.InvalidTokenError:
        return None, ("Invalid token", 401)
    except Exception as e:
        return None, (str(e), 401)


# ============================================================================
# DECORATORS FOR ROUTE PROTECTION
# ============================================================================

def require_auth(*allowed_roles):
    """
    Decorator to require authentication and check role permissions.

    Usage:
        @auth_bp.route("/protected_endpoint", methods=["POST"])
        @require_auth("registered", "subscribed")
        def protected_endpoint():
            return success_response({"message": "Success"})

    Args:
        *allowed_roles: Variable length role names (e.g., "admin", "subscribed")
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from api.routes.main import error_response

            # Extract token from request
            payload, error = extract_and_validate_token()
            if error:
                return error_response(error[0], error[1])

            # Resolve effective role from DB and active subscription window.
            user_role, access_rights = _resolve_effective_role_and_rights(payload)
            payload_dict = payload or {}
            if not user_role:
                user_role = payload_dict.get("role")
            if not user_role:
                return error_response("Role information missing in token", 401)

            # Check if user's role is allowed
            if allowed_roles and user_role not in allowed_roles:
                return error_response("Insufficient permissions for this action", 403)

            # Store payload + effective auth context for route handlers.
            setattr(request, "auth_payload", payload)
            setattr(request, "user_role", user_role)
            setattr(request, "user_id", payload_dict.get("user_id"))
            setattr(request, "subscription_access_rights", access_rights)

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_role(*roles):
    """
    Simpler alias for require_auth. Same functionality, different name.

    Usage:
        @require_role("admin")
        def admin_only_endpoint():
            pass
    """
    return require_auth(*roles)


def optional_auth(f):
    """
    Decorator for endpoints that work with OR without authentication.
    Sets request.auth_payload if token exists, otherwise None.

    Usage:
        @optional_auth
        def public_endpoint_with_optional_auth():
            if request.auth_payload:
                # User is authenticated
                user_role = request.user_role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try to extract token, but don't fail if missing
        payload, _ = extract_and_validate_token()
        role, rights = _resolve_effective_role_and_rights(payload)

        setattr(request, "auth_payload", payload)  # Will be None if no valid token
        setattr(request, "user_role", role if payload else None)
        setattr(request, "user_id", payload.get("user_id") if payload else None)
        setattr(request, "subscription_access_rights", rights if payload else None)

        return f(*args, **kwargs)

    return decorated_function


# ============================================================================
# ENTITLEMENT HELPERS (premium/free gating for the data API)
# Drive the DATA_VISIBILITY_RULES matrix above. Use with @optional_auth so the
# current user's role is available on request.user_role (None if anonymous).
# ============================================================================

# brand_rankings: registered/anonymous users only see the global top 10.
FREE_RANKING_LIMIT = 10
# top_posts: registered/anonymous users only see the single top post.
FREE_TOP_POSTS_LIMIT = 1
# The only time periods free/registered users may request (All Time + Last 30
# Days). Every other named window — and any custom start/end range — is premium.
FREE_PERIODS = {"all", "all_time", "max", "30d", "last_30d", "last_month"}


def _resolve_effective_role_and_rights(payload):
    if not payload:
        return None, None

    role = payload.get("role")
    rights = None
    user_id = payload.get("user_id")

    if not user_id:
        if role == UserRole.REGISTERED.value:
            from api.services.subscription_service import PACK_POLICIES
            rights = dict(PACK_POLICIES["starter"]["default_access_rights"])
        return role, rights

    try:
        from api.services.subscription_service import SubscriptionService

        user, active, active_rights = SubscriptionService.get_effective_access(user_id)
        role = user.role if user else role
        rights = active_rights
    except Exception:
        # Best-effort: never fail auth metadata enrichment.
        pass

    return role, rights


def current_user_role():
    """Best-effort role of the caller (from the Bearer/cookie JWT), or None when
    anonymous or the token is invalid. Lets a route apply entitlement rules
    without failing closed on unauthenticated access."""
    payload, _ = extract_and_validate_token()
    role, _ = _resolve_effective_role_and_rights(payload)
    return role


def current_subscription_access_rights():
    payload, _ = extract_and_validate_token()
    _, rights = _resolve_effective_role_and_rights(payload)
    return rights


def is_premium_role(role):
    """True for subscribed/admin — the roles with full data visibility."""
    return role in (UserRole.SUBSCRIBED.value, UserRole.ADMIN.value)


def ranking_access_error(role, period=None, start_date=None, end_date=None):
    """Entitlement check for ranking windows.

    - registered/free: existing free-tier restrictions.
    - subscribed: full access by default, with optional constraints if the active
      pack provides explicit access_rights.
    """
    rights = current_subscription_access_rights() if role == UserRole.SUBSCRIBED.value else None

    # Anonymous callers are allowed through route-level validation rules.
    if role is None:
        return None

    if is_premium_role(role):
        if rights:
            if (start_date or end_date) and not bool(rights.get("allow_custom_ranges", True)):
                return "Custom date ranges are not available for your current pack."
            if period and period.strip().lower() not in FREE_PERIODS and not bool(rights.get("allow_premium_periods", True)):
                return "This time period is not available for your current pack."
        return None

    if start_date or end_date:
        return "Custom date ranges are available on a paid plan."
    if period and period.strip().lower() not in FREE_PERIODS:
        return "This time period is available on a paid plan."
    return None


def limit_ranking_for_role(role, data):
    """Cap ranking rows based on role and optional pack-level rights."""
    if is_premium_role(role):
        if role == UserRole.SUBSCRIBED.value:
            rights = current_subscription_access_rights() or {}
            custom_limit = rights.get("ranking_limit")
            if isinstance(custom_limit, int) and custom_limit > 0 and isinstance(data, list):
                return data[:custom_limit]
        return data
    if isinstance(data, list):
        return data[:FREE_RANKING_LIMIT]
    return data


def top_posts_limit_for_role(role, requested):
    """Cap the number of top posts based on role and optional pack-level rights."""
    if is_premium_role(role):
        if role == UserRole.SUBSCRIBED.value:
            rights = current_subscription_access_rights() or {}
            max_items = rights.get("top_posts_limit")
            if isinstance(max_items, int) and max_items > 0:
                return min(max_items, requested)
        return requested
    return FREE_TOP_POSTS_LIMIT
