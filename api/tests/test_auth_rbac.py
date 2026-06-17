"""
Comprehensive Test Suite for Auth & RBAC System
Tests auth restoration, role-based access, and data visibility rules
"""

import pytest
import json
from datetime import datetime, timedelta, timezone

from api import db
from api.models.user_model import User
from api.services.auth_service import AuthService
from api.utils.permissions import (
    can_user_access_endpoint,
    get_data_visibility_for_role,
    UserRole,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def auth_headers(app, client):
    """Create auth headers for different roles"""
    headers = {}

    with app.app_context():
        for role in ["registered", "subscribed", "admin"]:
            # Check if user already exists
            user = User.query.filter_by(email=f"test_{role}@example.com").first()
            if not user:
                # Create a test user
                user = User(
                    first_name="Test",
                    last_name=role.capitalize(),
                    email=f"test_{role}@example.com",
                    role=role,
                    is_verified=True,
                )
                user.set_password("password123")
                db.session.add(user)
                db.session.commit()

            # Generate tokens
            tokens = AuthService.issue_token_pair(user)
            headers[role] = {
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "application/json",
            }

    return headers


@pytest.fixture
def public_headers():
    """Headers for public endpoints (no auth)"""
    return {"Content-Type": "application/json"}


# ============================================================================
# TESTS: Permission Matrix
# ============================================================================

class TestPermissionMatrix:
    """Test the permission matrix definitions"""

    def test_registered_can_access_public_ranking(self):
        """Registered users should access public endpoints"""
        assert can_user_access_endpoint(
            UserRole.REGISTERED.value, "public", "public_ranking"
        )

    def test_registered_can_access_get_entities(self):
        """Registered users should access get_all_entities"""
        assert can_user_access_endpoint(
            UserRole.REGISTERED.value, "data", "get_all_entities"
        )

    def test_registered_cannot_add_entity(self):
        """Registered users should NOT add entities (admin only)"""
        assert not can_user_access_endpoint(
            UserRole.REGISTERED.value, "data", "add_entity"
        )

    def test_subscribed_can_access_get_entities(self):
        """Subscribed users should access get_all_entities"""
        assert can_user_access_endpoint(
            UserRole.SUBSCRIBED.value, "data", "get_all_entities"
        )

    def test_admin_can_add_entity(self):
        """Admin users should add entities"""
        assert can_user_access_endpoint(UserRole.ADMIN.value, "data", "add_entity")

    def test_public_endpoint_accessible_to_all(self):
        """Public endpoints should be accessible without auth"""
        assert can_user_access_endpoint("any_role", "public", "public_ranking")


# ============================================================================
# TESTS: Data Visibility Rules
# ============================================================================

class TestDataVisibilityRules:
    """Test time-based data restrictions"""

    def test_registered_follower_history_visibility(self):
        """Registered users should see last month only"""
        visibility = get_data_visibility_for_role("follower_history", UserRole.REGISTERED.value)
        assert visibility == "last_month"

    def test_subscribed_follower_history_visibility(self):
        """Subscribed users should see full data"""
        visibility = get_data_visibility_for_role("follower_history", UserRole.SUBSCRIBED.value)
        assert visibility == "full"

    def test_admin_follower_history_visibility(self):
        """Admin users should see full data"""
        visibility = get_data_visibility_for_role("follower_history", UserRole.ADMIN.value)
        assert visibility == "full"

    def test_registered_brand_rankings_visibility(self):
        """Registered users should see top 10 only"""
        visibility = get_data_visibility_for_role("brand_rankings", UserRole.REGISTERED.value)
        assert visibility == "top_10_only"

    def test_subscribed_brand_rankings_visibility(self):
        """Subscribed users should see full rankings"""
        visibility = get_data_visibility_for_role("brand_rankings", UserRole.SUBSCRIBED.value)
        assert visibility == "full"

    def test_registered_interactions_visibility(self):
        """Registered users should see last month interactions only"""
        visibility = get_data_visibility_for_role(
            "interaction_history", UserRole.REGISTERED.value
        )
        assert visibility == "last_month"


# ============================================================================
# TESTS: Endpoint Auth (Integration Tests)
# ============================================================================

class TestEndpointAuth:
    """Test actual endpoint authentication"""

    def test_public_ranking_no_auth(self, client, public_headers):
        """Public ranking should be accessible without auth"""
        response = client.get("/api/public/ranking", headers=public_headers)
        # Should either return 200 or 404 (if no data), but NOT 401
        assert response.status_code in [200, 404]

    def test_get_user_data_requires_auth(self, client, public_headers):
        """get_user_data should require authentication"""
        response = client.post(
            "/api/auth/get_user_data", json={}, headers=public_headers
        )
        assert response.status_code == 401
        assert "No valid token" in response.get_json().get("error", "")

    def test_get_user_data_with_valid_token(self, client, auth_headers):
        """get_user_data should work with valid token"""
        response = client.post(
            "/api/auth/get_user_data", json={}, headers=auth_headers["registered"]
        )
        assert response.status_code == 200
        data = response.get_json().get("data", {})
        assert "user_id" in data
        assert "role" in data

    def test_add_entity_registered_user_denied(self, client, auth_headers):
        """Registered user should be denied from adding entities"""
        response = client.post(
            "/api/data/add_entity",
            json={
                "name": "Test Entity",
                "type": "company",
                "category_id": 1,
            },
            headers=auth_headers["registered"],
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.get_json().get("error", "")

    def test_get_all_entities_registered_allowed(self, client, auth_headers):
        """Registered user should be able to get entities"""
        response = client.get(
            "/api/data/get_all_entities", headers=auth_headers["registered"]
        )
        # Could be 200 or 404 depending on data, but should not be 401/403
        assert response.status_code in [200, 404]

    def test_get_all_entities_subscribed_allowed(self, client, auth_headers):
        """Subscribed user should be able to get entities"""
        response = client.get(
            "/api/data/get_all_entities", headers=auth_headers["subscribed"]
        )
        assert response.status_code in [200, 404]

    def test_logout_requires_auth(self, client, public_headers):
        """Logout should require authentication"""
        response = client.post("/api/auth/logout", json={}, headers=public_headers)
        assert response.status_code == 401


# ============================================================================
# TESTS: Token Validation
# ============================================================================

class TestTokenValidation:
    """Test token extraction and validation"""

    def test_bearer_token_extraction(self, client, auth_headers):
        """Bearer token should be extracted from Authorization header"""
        response = client.post(
            "/api/auth/get_user_data", json={}, headers=auth_headers["registered"]
        )
        assert response.status_code == 200

    def test_invalid_token_rejected(self, client, public_headers):
        """Invalid token should be rejected"""
        headers = public_headers.copy()
        headers["Authorization"] = "Bearer invalid.token.here"
        response = client.post("/api/auth/get_user_data", json={}, headers=headers)
        assert response.status_code == 401


# ============================================================================
# TESTS: Role-Based Endpoint Access
# ============================================================================

class TestRoleBasedAccess:
    """Test role-based access control across different endpoints"""

    def test_register_mail_public(self, client, public_headers):
        """register_mail should be public"""
        response = client.post(
            "/api/auth/register_mail",
            json={"email": "newemail@example.com"},
            headers=public_headers,
        )
        # Could fail due to validation, but not due to auth
        assert response.status_code != 401

    def test_login_public(self, client, public_headers):
        """login should be public"""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
            headers=public_headers,
        )
        # Could be 401 due to invalid credentials, but not due to missing auth
        assert response.status_code != 403

    def test_complete_profile_requires_auth(self, client, public_headers):
        """complete_profile should require auth"""
        response = client.post(
            "/api/auth/complete_profile",
            json={"phone_number": "+1234567890", "profession": "ceo"},
            headers=public_headers,
        )
        assert response.status_code == 401

    def test_complete_profile_with_auth(self, client, auth_headers):
        """complete_profile should work with auth"""
        response = client.post(
            "/api/auth/complete_profile",
            json={"phone_number": "+1234567890", "profession": "ceo"},
            headers=auth_headers["registered"],
        )
        assert response.status_code in [200, 404]  # Could fail on DB, but not auth


# ============================================================================
# TESTS: Multiple Role Checks
# ============================================================================

class TestMultipleRoles:
    """Test endpoints that allow multiple roles"""

    def test_get_entities_all_authenticated_roles(self, client, auth_headers):
        """get_all_entities should work for all authenticated roles"""
        for role in ["registered", "subscribed", "admin"]:
            response = client.get(
                "/api/data/get_all_entities", headers=auth_headers[role]
            )
            assert response.status_code in [200, 404]

    def test_refresh_token_all_authenticated_roles(self, client, auth_headers):
        """refresh_token endpoint should work for all authenticated roles"""
        for role in ["registered", "subscribed", "admin"]:
            response = client.post(
                "/api/auth/refresh_token", json={}, headers=auth_headers[role]
            )
            # Should not fail due to auth (might fail due to invalid token format)
            assert response.status_code != 403


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
