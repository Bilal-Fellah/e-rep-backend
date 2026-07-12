"""
Simplified Integration Tests for Auth Decorator
Tests the @require_auth decorator and auth flow
"""

import pytest
from unittest.mock import patch, MagicMock
from api.utils.permissions import require_auth, extract_and_validate_token
import jwt
import os
from datetime import datetime, timedelta, timezone


# ============================================================================
# TESTS: Token Extraction and Validation
# ============================================================================

class TestTokenExtraction:
    """Test token extraction and validation helper"""

    def test_no_token_provided(self):
        """Should return error when no token is provided"""
        with patch('api.utils.permissions._extract_token', return_value=None):
            payload, error = extract_and_validate_token()
            assert payload is None
            assert error is not None
            assert error[1] == 401

    def test_invalid_token_format(self):
        """Should return error for invalid token format"""
        with patch('api.utils.permissions._extract_token', return_value="invalid.token"):
            with patch('jwt.decode', side_effect=jwt.InvalidTokenError):
                payload, error = extract_and_validate_token()
                assert payload is None
                assert error is not None
                assert error[1] == 401

    def test_expired_token(self):
        """Should return error for expired token"""
        with patch('api.utils.permissions._extract_token', return_value="expired.token"):
            with patch('jwt.decode', side_effect=jwt.ExpiredSignatureError):
                payload, error = extract_and_validate_token()
                assert payload is None
                assert error is not None
                assert error[1] == 401

    def test_valid_token(self):
        """Should extract valid token"""
        valid_payload = {
            "user_id": 123,
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        with patch('api.utils.permissions._extract_token', return_value="valid.token"):
            with patch('jwt.decode', return_value=valid_payload):
                payload, error = extract_and_validate_token()
                assert payload == valid_payload
                assert error is None


# ============================================================================
# TESTS: Require Auth Decorator
# ============================================================================

class TestRequireAuthDecorator:
    """Test the @require_auth decorator"""

    def test_decorator_requires_token(self):
        """Decorator should reject request without valid token"""
        @require_auth("admin")
        def protected_route():
            return {"success": True}

        with patch('api.utils.permissions.extract_and_validate_token',
                   return_value=(None, ("No valid token", 401))):
            with patch('api.routes.main.error_response', return_value=("error", 401)):
                result = protected_route()
                # Should call error_response since no valid token
                assert result == ("error", 401)

    def test_decorator_requires_matching_role(self):
        """Decorator should reject if user role doesn't match allowed roles"""
        @require_auth("admin")
        def admin_only_route():
            return {"success": True}

        # User has "registered" role but "admin" is required
        payload = {"user_id": 1, "role": "registered"}
        
        with patch('api.utils.permissions.extract_and_validate_token',
                   return_value=(payload, None)):
            with patch('api.routes.main.error_response', return_value=("forbidden", 403)):
                result = admin_only_route()
                # Should call error_response for insufficient permissions
                assert result == ("forbidden", 403)

    def test_decorator_allows_matching_role(self):
        """Decorator should allow request with matching role"""
        @require_auth("admin")
        def admin_route():
            return {"success": True, "user_id": 1}

        payload = {"user_id": 1, "role": "admin"}
        
        from flask import Flask
        app = Flask("test_app")
        with patch('api.utils.permissions.extract_and_validate_token',
                   return_value=(payload, None)):
            with patch('api.routes.main.error_response'):
                with app.test_request_context():
                    result = admin_route()
                    # Should call the actual function and return success
                    assert result == {"success": True, "user_id": 1}

    def test_decorator_allows_multiple_roles(self):
        """Decorator should allow if user role in multiple allowed roles"""
        @require_auth("admin", "subscribed")
        def multi_role_route():
            return {"success": True}

        payload = {"user_id": 1, "role": "subscribed"}
        
        from flask import Flask
        app = Flask("test_app")
        with patch('api.utils.permissions.extract_and_validate_token',
                   return_value=(payload, None)):
            with app.test_request_context():
                result = multi_role_route()
                assert result == {"success": True}


# ============================================================================
# TESTS: Permission Matrix Logic
# ============================================================================

class TestPermissionMatrixLogic:
    """Test the core permission matrix functions"""

    def test_public_endpoints_accessible_without_auth(self):
        """Public endpoints should not require any role"""
        from api.utils.permissions import can_user_access_endpoint
        
        # Anyone (including unauthenticated) can access public endpoints
        assert can_user_access_endpoint("", "public", "public_ranking")
        assert can_user_access_endpoint(None, "public", "public_ranking")
        assert can_user_access_endpoint("any_role", "public", "public_ranking")

    def test_admin_only_endpoints(self):
        """Admin-only endpoints should reject non-admin users"""
        from api.utils.permissions import can_user_access_endpoint
        
        # Admin can access
        assert can_user_access_endpoint("admin", "data", "add_entity")
        
        # Non-admin cannot
        assert not can_user_access_endpoint("registered", "data", "add_entity")
        assert not can_user_access_endpoint("subscribed", "data", "add_entity")

    def test_authenticated_user_endpoints(self):
        """Endpoints requiring authentication should reject unauthenticated users"""
        from api.utils.permissions import can_user_access_endpoint
        
        # Authenticated users can access
        assert can_user_access_endpoint("registered", "data", "get_all_entities")
        assert can_user_access_endpoint("subscribed", "data", "get_all_entities")
        assert can_user_access_endpoint("admin", "data", "get_all_entities")


# ============================================================================
# TESTS: Data Visibility Logic
# ============================================================================

class TestDataVisibilityLogic:
    """Test data visibility rules for different roles"""

    def test_registered_user_data_restrictions(self):
        """Registered users should get restricted data visibility"""
        from api.utils.permissions import get_data_visibility_for_role
        
        # Registered should get limited time windows
        assert get_data_visibility_for_role("follower_history", "registered") == "last_month"
        assert get_data_visibility_for_role("interaction_history", "registered") == "last_month"
        assert get_data_visibility_for_role("top_posts", "registered") == "last_month"
        
        # Rankings should be top 10 only
        assert get_data_visibility_for_role("brand_rankings", "registered") == "top_10_only"

    def test_subscribed_user_full_access(self):
        """Subscribed users should get full data visibility"""
        from api.utils.permissions import get_data_visibility_for_role
        
        # Subscribed should get full access
        assert get_data_visibility_for_role("follower_history", "subscribed") == "full"
        assert get_data_visibility_for_role("interaction_history", "subscribed") == "full"
        assert get_data_visibility_for_role("brand_rankings", "subscribed") == "full"

    def test_admin_user_full_access(self):
        """Admin users should get full data visibility"""
        from api.utils.permissions import get_data_visibility_for_role
        
        # Admin should get full access
        assert get_data_visibility_for_role("follower_history", "admin") == "full"
        assert get_data_visibility_for_role("interaction_history", "admin") == "full"
        assert get_data_visibility_for_role("brand_rankings", "admin") == "full"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
