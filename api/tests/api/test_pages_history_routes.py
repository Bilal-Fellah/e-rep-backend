"""API route tests for pages_history monitoring endpoints."""

from datetime import datetime, timedelta, timezone
import json
import os
import jwt
import pytest


def _make_auth_header(role="registered", user_id=1):
    secret = os.environ.get("SECRET_KEY", "test-secret")
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_get_pages_history_unauthenticated(client):
    response = client.get("/api/data/pages_history")
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_get_pages_history_success(client, monkeypatch):
    headers = _make_auth_header("registered")
    mock_result = {
        "items": [
            {
                "id": 1,
                "recorded_at": "2026-08-09T04:00:00+00:00",
                "page_id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31",
                "page_name": "Test Page",
                "page_link": "https://facebook.com/test",
                "platform": "facebook",
                "brand_id": 10,
                "brand_name": "Test Brand",
                "data": {"followers": 5000},
            }
        ],
        "total": 1,
        "page": 1,
        "per_page": 20,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False,
    }

    monkeypatch.setattr(
        "api.routes.data.pages_history.PageHistoryService.get_filtered_history",
        lambda **kwargs: mock_result,
    )

    response = client.get("/api/data/pages_history?platform=facebook", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["brand_name"] == "Test Brand"

    # Test alias route /get_pages_history
    response_alias = client.get("/api/data/get_pages_history?platform=facebook", headers=headers)
    assert response_alias.status_code == 200


def test_get_pages_history_by_id_success(client, monkeypatch):
    headers = _make_auth_header("registered")
    mock_item = {
        "id": 42,
        "recorded_at": "2026-08-09T04:00:00+00:00",
        "page_id": "3f5d7c6a-8b10-54c3-a2b5-1c77d33f9e31",
        "page_name": "Test Page",
        "page_link": "https://facebook.com/test",
        "platform": "facebook",
        "brand_id": 10,
        "brand_name": "Test Brand",
        "data": {"followers": 5000},
    }

    monkeypatch.setattr(
        "api.routes.data.pages_history.PageHistoryService.get_history_by_id",
        lambda history_id: mock_item if history_id == 42 else None,
    )

    response = client.get("/api/data/pages_history/42", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["id"] == 42

    # Test alias route /get_pages_history_by_id?id=42
    response_alias = client.get("/api/data/get_pages_history_by_id?id=42", headers=headers)
    assert response_alias.status_code == 200
    assert response_alias.get_json()["data"]["id"] == 42


def test_get_pages_history_by_id_not_found(client, monkeypatch):
    headers = _make_auth_header("registered")
    monkeypatch.setattr(
        "api.routes.data.pages_history.PageHistoryService.get_history_by_id",
        lambda history_id: None,
    )

    response = client.get("/api/data/pages_history/999", headers=headers)
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "No pages_history record found" in data["error"]


def test_get_pages_history_options(client, monkeypatch):
    headers = _make_auth_header("registered")
    mock_options = {
        "platforms": ["facebook", "instagram"],
        "brands": [{"id": 10, "name": "Test Brand"}],
        "date_range": {"min_date": "2026-01-01T00:00:00", "max_date": "2026-08-09T00:00:00"},
        "total_records": 100,
    }

    monkeypatch.setattr(
        "api.routes.data.pages_history.PageHistoryService.get_filter_options",
        lambda: mock_options,
    )

    response = client.get("/api/data/pages_history/options", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "facebook" in data["data"]["platforms"]


def test_get_pages_history_summary(client, monkeypatch):
    headers = _make_auth_header("registered")
    mock_summary = {
        "total_records": 500,
        "records_today": 10,
        "records_last_7_days": 70,
        "records_last_30_days": 300,
        "by_platform": {"facebook": 200, "instagram": 300},
        "active_pages_monitored": 25,
    }

    monkeypatch.setattr(
        "api.routes.data.pages_history.PageHistoryService.get_monitoring_summary",
        lambda: mock_summary,
    )

    response = client.get("/api/data/pages_history/summary", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["total_records"] == 500
    assert data["data"]["active_pages_monitored"] == 25
