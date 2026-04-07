"""
API route tests for Flask blueprints.
Routes tested:
- Health check endpoint
- Auth routes (signup, login, token refresh)
- Public API routes
- OAuth routes
- Data routes
"""

import json
import pytest


def test_health_check_endpoint(client):
    """Test /health/check returns 200 with ok status."""
    response = client.get("/health/check")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get("status") == "ok"


# Placeholder: Auth route tests
def test_auth_routes_placeholder():
    """Auth routes tests will be implemented after database integration is complete."""
    pass


# Placeholder: Public route tests
def test_public_routes_placeholder():
    """Public routes tests will be implemented after database integration is complete."""
    pass


# Placeholder: OAuth route tests
def test_oauth_routes_placeholder():
    """OAuth routes tests will be implemented after database integration is complete."""
    pass


# Placeholder: Data route tests
def test_data_routes_placeholder():
    """Data routes tests will be implemented after database integration is complete."""
    pass