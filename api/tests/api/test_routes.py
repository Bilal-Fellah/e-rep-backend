"""API route tests for flask blueprints with mocked services/repositories."""

import json
from types import SimpleNamespace

import pytest


def test_health_check_endpoint(client):
    """Test /health/check returns 200 with ok status."""
    response = client.get("/health/check")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get("status") == "ok"


def test_auth_register_user_validation_paths(client):
    response = client.post("/api/auth/register_user", json={})
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False

    response = client.post(
        "/api/auth/register_user",
        json={
            "full_name": "John Doe",
            "email": "bad-email",
            "password": "12345678",
            "phone_number": "+212612345678",
            "profession": "other",
        },
    )
    assert response.status_code == 400
    assert "Invalid email format" in response.get_json()["error"]


def test_auth_login_invalid_email_and_invalid_credentials(client, monkeypatch):
    response = client.post("/api/auth/login", json={"email": "bad", "password": "x"})
    assert response.status_code == 400

    fake_user = SimpleNamespace(check_password=lambda _pwd: False)
    monkeypatch.setattr("api.routes.auth_routes.UserRepository.find_by_email", lambda email: fake_user)
    response = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_public_ranking_formats_top_global_and_category_extras(client, monkeypatch):
    ranking = [
        {"entity_id": 1, "category": "tech", "rank": 1},
        {"entity_id": 2, "category": "tech", "rank": 2},
        {"entity_id": 3, "category": "food", "rank": 3},
    ]
    monkeypatch.setattr("api.routes.public_routes.PageHistoryRepository.get_public_ranking", lambda: ranking)

    response = client.get("/api/public/ranking")
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert len(payload["top_global"]) == 3
    # food top entry is already in top_global, so no extra category record is appended.
    assert payload["top_by_category"] == []


def test_public_ranking_empty_returns_404(client, monkeypatch):
    monkeypatch.setattr("api.routes.public_routes.PageHistoryRepository.get_public_ranking", lambda: [])
    response = client.get("/api/public/ranking")
    assert response.status_code == 404


def test_oauth_finalize_google_login_invalid_code(client, monkeypatch):
    monkeypatch.setattr("api.routes.google_auth.consume_login_code", lambda code: None)
    response = client.post("/api/oauth/google/finalize", json={"code": "bad-code"})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_data_get_entity_history_invalid_date_and_success(client, monkeypatch):
    monkeypatch.setattr("api.routes.data.influence_history._extract_token", lambda _name: "tok")
    monkeypatch.setattr("api.routes.data.influence_history.jwt.decode", lambda token, secret, algorithms: {"role": "registered"})

    response = client.get("/api/data/get_entity_history?entity_id=5&date=2026-99-99")
    assert response.status_code == 400

    history_rows = [SimpleNamespace(id=1, page_id="p1", data={}, recorded_at="2026-01-01T00:00:00Z")]
    monkeypatch.setattr(
        "api.routes.data.influence_history.InfluenceHistoryService.get_entity_history",
        lambda entity_id, date_str=None: history_rows,
    )
    response = client.get("/api/data/get_entity_history?entity_id=5&date=2026-01-01")
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_data_get_competitors_interaction_stats_parsing_and_404(client, monkeypatch):
    captured = {}

    def _service(entity_ids, start_date=None):
        captured["entity_ids"] = entity_ids
        captured["start_date"] = start_date
        return []

    monkeypatch.setattr(
        "api.routes.data.influence_history.InfluenceHistoryService.get_competitors_interaction_stats",
        _service,
    )

    response = client.post(
        "/api/data/get_competitors_interaction_stats",
        json={"entity_ids": [1, 2], "start_date": "2026-01-01T00:00:00Z"},
    )

    assert response.status_code == 404
    assert captured["entity_ids"] == [1, 2]
    assert captured["start_date"] is not None