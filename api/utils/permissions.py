# Centralized Role-Based Access Control (RBAC) Configuration
# Single source of truth for all role-based permissions in the application

from enum import Enum
from functools import wraps
from flask import request, jsonify
import jwt
import os
from api.repositories.user_repository import UserRepository
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

            # Get user role from token
            user_role = payload.get("role")
            if not user_role:
                return error_response("Role information missing in token", 401)

            # Check if user's role is allowed
            if allowed_roles and user_role not in allowed_roles:
                return error_response("Insufficient permissions for this action", 403)

            # Store payload in request context for use in route handler
            request.auth_payload = payload
            request.user_role = user_role
            request.user_id = payload.get("user_id")

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

        request.auth_payload = payload  # Will be None if no valid token
        request.user_role = payload.get("role") if payload else None
        request.user_id = payload.get("user_id") if payload else None

        return f(*args, **kwargs)

    return decorated_function
