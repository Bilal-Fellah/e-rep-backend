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


def test_auth_login_success_returns_tokens(client, monkeypatch):
    user = SimpleNamespace(id=7, role="registered", check_password=lambda pwd: pwd == "ok")

    monkeypatch.setattr("api.routes.auth_routes.UserRepository.find_by_email", lambda email: user)
    monkeypatch.setattr(
        "api.routes.auth_routes.AuthService.issue_token_pair",
        lambda user: {
            "access_token": "a-token",
            "refresh_token": "r-token",
            "refresh_token_exp": "exp",
        },
    )

    persisted = {}
    monkeypatch.setattr(
        "api.routes.auth_routes.AuthService.persist_refresh_token",
        lambda user_id, token, exp: persisted.update({"user_id": user_id, "token": token, "exp": exp}),
    )
    monkeypatch.setattr(
        "api.routes.auth_routes.AuthService.build_auth_response",
        lambda user, access_token, refresh_token: {
            "user_id": user.id,
            "user_role": user.role,
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    )

    response = client.post("/api/auth/login", json={"email": "a@b.com", "password": "ok"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["access_token"] == "a-token"
    assert persisted["user_id"] == 7


def test_auth_refresh_token_missing_returns_400(client):
    response = client.post("/api/auth/refresh_token", json={})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing refresh token"


def test_public_ranking_formats_top_global(client, monkeypatch):
    ranking = [{"entity_id": i, "category": "tech", "rank": i} for i in range(1, 13)]
    monkeypatch.setattr("api.routes.public_routes.PageHistoryRepository.get_public_ranking", lambda: ranking)

    response = client.get("/api/public/ranking")
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert len(payload["top_global"]) == 10
    assert payload["top_global"][0]["entity_id"] == 1
    assert payload["top_global"][-1]["entity_id"] == 10
    assert "top_by_category" not in payload


def test_public_ranking_empty_returns_404(client, monkeypatch):
    monkeypatch.setattr("api.routes.public_routes.PageHistoryRepository.get_public_ranking", lambda: [])
    response = client.get("/api/public/ranking")
    assert response.status_code == 404


def test_oauth_finalize_google_login_invalid_code(client, monkeypatch):
    monkeypatch.setattr("api.routes.google_auth.consume_login_code", lambda code: None)
    response = client.post("/api/oauth/google/finalize", json={"code": "bad-code"})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_data_add_entity_missing_fields_and_success(client, monkeypatch):
    response = client.post("/api/data/add_entity", json={"name": "x"})
    assert response.status_code == 400

    entity = SimpleNamespace(id=1, name="acme", type="brand")
    entity_category = SimpleNamespace(entity_id=1, category_id=2)
    monkeypatch.setattr(
        "api.routes.data.entity.EntityService.create_entity",
        lambda name, entity_type, category_id: (entity, entity_category),
    )
    response = client.post(
        "/api/data/add_entity",
        json={"name": " Acme ", "type": "Brand", "category_id": 2},
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["entity"]["id"] == 1
    assert payload["entity_category"]["category_id"] == 2


def test_data_get_entity_likes_history_validation_not_found_and_success(client, monkeypatch):
    response = client.get("/api/data/get_entity_likes_history")
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.entity.EntityService.get_entity_likes_history", lambda entity_id, start_date=None: [])
    response = client.get("/api/data/get_entity_likes_history?entity_id=1")
    assert response.status_code == 404

    captured = {}

    def _service(entity_id, start_date=None):
        captured["entity_id"] = entity_id
        captured["start_date"] = start_date
        return [
            {
                "page_id": "p1",
                "platform": "instagram",
                "date": "2026-01-02",
                "likes_gained": 12,
            }
        ]

    monkeypatch.setattr("api.routes.data.entity.EntityService.get_entity_likes_history", _service)
    response = client.get("/api/data/get_entity_likes_history?entity_id=5&start_date=2026-01-01")
    assert response.status_code == 200
    assert captured["entity_id"] == 5
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["likes_gained"] == 12


def test_data_get_entity_likes_history_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.entity.EntityService.get_entity_likes_history",
        lambda entity_id, start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )
    response = client.get("/api/data/get_entity_likes_history?entity_id=5&start_date=bad-date")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request data"


def test_data_compare_entities_likes_validation_not_found_and_success(client, monkeypatch):
    response = client.post("/api/data/compare_entities_likes", json={})
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.entity.EntityService.compare_entities_likes", lambda entity_ids, start_date=None: None)
    response = client.post("/api/data/compare_entities_likes", json={"entity_ids": [1]})
    assert response.status_code == 404

    captured = {}

    def _service(entity_ids, start_date=None):
        captured["entity_ids"] = entity_ids
        captured["start_date"] = start_date
        return {
            "A": {
                "entity_id": 1,
                "records": [
                    {
                        "page_id": "p1",
                        "platform": "x",
                        "date": "2026-01-02",
                        "likes_gained": 4,
                    }
                ],
            }
        }

    monkeypatch.setattr("api.routes.data.entity.EntityService.compare_entities_likes", _service)
    response = client.post(
        "/api/data/compare_entities_likes",
        json={"entity_ids": [1, 2], "start_date": "2026-01-01"},
    )

    assert response.status_code == 200
    assert captured["entity_ids"] == [1, 2]
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"]["A"]["records"][0]["likes_gained"] == 4


def test_data_compare_entities_likes_invalid_payload_shapes_return_400(client):
    response = client.post("/api/data/compare_entities_likes", json={"entity_ids": "1,2"})
    assert response.status_code == 400

    response = client.post("/api/data/compare_entities_likes", json={"entity_ids": []})
    assert response.status_code == 400


def test_data_compare_entities_likes_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.entity.EntityService.compare_entities_likes",
        lambda entity_ids, start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )

    response = client.post(
        "/api/data/compare_entities_likes",
        json={"entity_ids": [1, 2], "start_date": "bad-date"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request data"


def test_data_get_entity_comments_history_validation_not_found_and_success(client, monkeypatch):
    response = client.get("/api/data/get_entity_comments_history")
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.entity.EntityService.get_entity_comments_history", lambda entity_id, start_date=None: [])
    response = client.get("/api/data/get_entity_comments_history?entity_id=1")
    assert response.status_code == 404

    captured = {}

    def _service(entity_id, start_date=None):
        captured["entity_id"] = entity_id
        captured["start_date"] = start_date
        return [
            {
                "page_id": "p1",
                "platform": "instagram",
                "date": "2026-01-02",
                "comments_gained": 7,
            }
        ]

    monkeypatch.setattr("api.routes.data.entity.EntityService.get_entity_comments_history", _service)
    response = client.get("/api/data/get_entity_comments_history?entity_id=5&start_date=2026-01-01")
    assert response.status_code == 200
    assert captured["entity_id"] == 5
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["comments_gained"] == 7


def test_data_get_entity_comments_history_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.entity.EntityService.get_entity_comments_history",
        lambda entity_id, start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )
    response = client.get("/api/data/get_entity_comments_history?entity_id=5&start_date=bad-date")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request data"


def test_data_compare_entities_comments_validation_not_found_and_success(client, monkeypatch):
    response = client.post("/api/data/compare_entities_comments", json={})
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.entity.EntityService.compare_entities_comments", lambda entity_ids, start_date=None: None)
    response = client.post("/api/data/compare_entities_comments", json={"entity_ids": [1]})
    assert response.status_code == 404

    captured = {}

    def _service(entity_ids, start_date=None):
        captured["entity_ids"] = entity_ids
        captured["start_date"] = start_date
        return {
            "A": {
                "entity_id": 1,
                "records": [
                    {
                        "page_id": "p1",
                        "platform": "x",
                        "date": "2026-01-02",
                        "comments_gained": 3,
                    }
                ],
            }
        }

    monkeypatch.setattr("api.routes.data.entity.EntityService.compare_entities_comments", _service)
    response = client.post(
        "/api/data/compare_entities_comments",
        json={"entity_ids": [1, 2], "start_date": "2026-01-01"},
    )

    assert response.status_code == 200
    assert captured["entity_ids"] == [1, 2]
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"]["A"]["records"][0]["comments_gained"] == 3


def test_data_compare_entities_comments_invalid_payload_shapes_return_400(client):
    response = client.post("/api/data/compare_entities_comments", json={"entity_ids": "1,2"})
    assert response.status_code == 400

    response = client.post("/api/data/compare_entities_comments", json={"entity_ids": []})
    assert response.status_code == 400


def test_data_compare_entities_comments_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.entity.EntityService.compare_entities_comments",
        lambda entity_ids, start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )

    response = client.post(
        "/api/data/compare_entities_comments",
        json={"entity_ids": [1, 2], "start_date": "bad-date"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request data"


def test_data_get_post_validation_and_success(client, monkeypatch):
    response = client.get("/api/data/get_post?page_id=p1&platform=instagram")
    assert response.status_code == 400

    fake_post = SimpleNamespace(to_dict=lambda: {"post_id": "p1_1", "platform": "instagram"})
    monkeypatch.setattr("api.routes.data.posts.PostService.get_post", lambda page_id, platform, post_id: fake_post)
    response = client.get("/api/data/get_post?page_id=p1&platform=instagram&post_id=1")
    assert response.status_code == 200
    assert response.get_json()["data"]["post_id"] == "p1_1"


def test_data_get_posts_by_entity_validation_and_not_found(client, monkeypatch):
    response = client.get("/api/data/get_posts_by_entity")
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.posts.PostService.get_posts_by_entity", lambda entity_id, platform=None: [])
    response = client.get("/api/data/get_posts_by_entity?entity_id=12")
    assert response.status_code == 404


def test_data_create_note_validation_and_success(client, monkeypatch):
    response = client.post(
        "/api/data/create_note",
        json={"content": "x", "target_type": "bad", "target_id": "1", "user_id": 1},
    )
    assert response.status_code == 400

    monkeypatch.setattr("api.routes.data.note.PostRepository.get_by_id", lambda post_id: SimpleNamespace(id=post_id))
    monkeypatch.setattr("api.routes.data.note.UserRepository.get_by_id", lambda user_id: SimpleNamespace(id=user_id))
    created_note = SimpleNamespace(
        id=10,
        author_id=1,
        title="n",
        content="hello",
        target_type="post",
        target_id="88",
        context_data=None,
        visibility="private",
        status="active",
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00Z"),
        updated_at=None,
    )
    monkeypatch.setattr("api.routes.data.note.NoteRepository.create", lambda **kwargs: created_note)

    response = client.post(
        "/api/data/create_note",
        json={"content": "hello", "target_type": "post", "target_id": "88", "user_id": 1},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == 10


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


def test_data_get_interactions_ranking_not_found_and_success(client, monkeypatch):
    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_interactions_ranking", lambda start_date=None: [])
    response = client.get("/api/data/get_interactions_ranking")
    assert response.status_code == 404

    captured = {}

    def _service(start_date=None):
        captured["start_date"] = start_date
        return [
            {
                "entity_id": 1,
                "entity_name": "A Corp",
                "category": "auto",
                "root_category": "business",
                "rank": 1,
                "total_score": 12.3,
                "platforms": {},
            }
        ]

    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_interactions_ranking", _service)
    response = client.get("/api/data/get_interactions_ranking?start_date=2026-01-01")
    assert response.status_code == 200
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["entity_name"] == "A Corp"
    assert response.get_json()["data"][0]["category"] == "auto"
    assert response.get_json()["data"][0]["root_category"] == "business"


def test_data_get_interactions_ranking_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.influence_history.InfluenceHistoryService.get_interactions_ranking",
        lambda start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )

    response = client.get("/api/data/get_interactions_ranking?start_date=bad-date")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request data"


def test_data_get_likes_ranking_not_found_and_success(client, monkeypatch):
    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_likes_ranking", lambda start_date=None: [])
    response = client.get("/api/data/get_likes_ranking")
    assert response.status_code == 404

    captured = {}

    def _service(start_date=None):
        captured["start_date"] = start_date
        return [
            {
                "entity_id": 1,
                "entity_name": "A Corp",
                "category": "auto",
                "root_category": "business",
                "rank": 1,
                "total_likes": 120,
                "platforms": {},
            }
        ]

    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_likes_ranking", _service)
    response = client.get("/api/data/get_likes_ranking?start_date=2026-01-01")
    assert response.status_code == 200
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["entity_name"] == "A Corp"
    assert response.get_json()["data"][0]["category"] == "auto"
    assert response.get_json()["data"][0]["root_category"] == "business"


def test_data_get_comments_ranking_not_found_and_success(client, monkeypatch):
    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_comments_ranking", lambda start_date=None: [])
    response = client.get("/api/data/get_comments_ranking")
    assert response.status_code == 404

    captured = {}

    def _service(start_date=None):
        captured["start_date"] = start_date
        return [
            {
                "entity_id": 1,
                "entity_name": "A Corp",
                "category": "auto",
                "root_category": "business",
                "rank": 1,
                "total_comments": 65,
                "platforms": {},
            }
        ]

    monkeypatch.setattr("api.routes.data.influence_history.InfluenceHistoryService.get_comments_ranking", _service)
    response = client.get("/api/data/get_comments_ranking?start_date=2026-01-01")
    assert response.status_code == 200
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["entity_name"] == "A Corp"
    assert response.get_json()["data"][0]["category"] == "auto"
    assert response.get_json()["data"][0]["root_category"] == "business"


def test_data_get_likes_and_comments_ranking_invalid_start_date_returns_400(client, monkeypatch):
    monkeypatch.setattr(
        "api.routes.data.influence_history.InfluenceHistoryService.get_likes_ranking",
        lambda start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )
    monkeypatch.setattr(
        "api.routes.data.influence_history.InfluenceHistoryService.get_comments_ranking",
        lambda start_date=None: (_ for _ in ()).throw(ValueError("Invalid date format")),
    )

    likes_response = client.get("/api/data/get_likes_ranking?start_date=bad-date")
    comments_response = client.get("/api/data/get_comments_ranking?start_date=bad-date")

    assert likes_response.status_code == 400
    assert likes_response.get_json()["error"] == "Invalid request data"
    assert comments_response.status_code == 400
    assert comments_response.get_json()["error"] == "Invalid request data"


def test_data_get_competitors_interaction_stats_invalid_payload_returns_400(client):
    response = client.post("/api/data/get_competitors_interaction_stats", json={"start_date": "2026-01-01T00:00:00Z"})
    assert response.status_code == 400


def test_data_platform_history_missing_param_returns_400(client):
    response = client.get("/api/data/get_platform_history")
    assert response.status_code == 400


def test_testing_entity_daily_raw_metrics_validation_and_success(client, monkeypatch):
    response = client.get("/api/testing/entity_daily_raw_metrics")
    assert response.status_code == 400

    response = client.get("/api/testing/entity_daily_raw_metrics?entity_id=5&metric=shares")
    assert response.status_code == 400

    monkeypatch.setattr(
        "api.routes.testing.entity_debug._fetch_entity_daily_raw_metrics",
        lambda entity_id, metric="likes", start_date=None: [],
    )
    response = client.get("/api/testing/entity_daily_raw_metrics?entity_id=5&metric=likes")
    assert response.status_code == 404

    captured = {}

    def _service(entity_id, metric="likes", start_date=None):
        captured["entity_id"] = entity_id
        captured["metric"] = metric
        captured["start_date"] = start_date
        return [
            {
                "page_id": "p-1",
                "platform": "instagram",
                "date": "2026-01-10",
                "likes_raw": 42,
                "posts_count": 2,
                "per_post": {"post-a": 30, "post-b": 12},
            }
        ]

    monkeypatch.setattr("api.routes.testing.entity_debug._fetch_entity_daily_raw_metrics", _service)
    response = client.get("/api/testing/entity_daily_raw_metrics?entity_id=5&metric=likes&start_date=2026-01-01")

    assert response.status_code == 200
    assert captured["entity_id"] == 5
    assert captured["metric"] == "likes"
    assert captured["start_date"] == "2026-01-01"
    assert response.get_json()["data"][0]["likes_raw"] == 42