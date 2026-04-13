from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest

from api.services.auth_service import AuthService
from api.services.entity_service import EntityService
from api.services.influence_history_service import InfluenceHistoryService
from api.services.page_service import PageService
from api.services.post_service import PostService
from api.utils.data_keys import platform_metrics


def test_auth_signup_raises_if_email_exists(monkeypatch):
    monkeypatch.setattr("api.services.auth_service.UserRepository.find_by_email", lambda _email: object())

    with pytest.raises(ValueError, match="Email already exists"):
        AuthService.signup("John", "john@doe.com", "secret")


def test_auth_signup_creates_user_sets_password_and_saves(monkeypatch):
    created = {}

    class FakeUser:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.password_set = None

        def set_password(self, password):
            self.password_set = password

    monkeypatch.setattr("api.services.auth_service.UserRepository.find_by_email", lambda _email: None)
    monkeypatch.setattr("api.services.auth_service.User", FakeUser)

    def _save_user(user):
        created["user"] = user

    monkeypatch.setattr("api.services.auth_service.UserRepository.save_user", _save_user)

    user = AuthService.signup("John", "john@doe.com", "top-secret", last_name="Smith", phone_number="+2126")

    assert user.kwargs["first_name"] == "John"
    assert user.kwargs["email"] == "john@doe.com"
    assert user.password_set == "top-secret"
    assert created["user"] is user


def test_auth_login_success_and_invalid_credentials(monkeypatch):
    fake_user = SimpleNamespace(id=8, role="registered")
    fake_user.check_password = lambda pwd: pwd == "ok-pass"

    monkeypatch.setattr("api.services.auth_service.UserRepository.find_by_email", lambda _email: fake_user)
    monkeypatch.setattr("api.services.auth_service.jwt.encode", lambda payload, key, algorithm: f"jwt:{payload['user_id']}:{algorithm}")

    token = AuthService.login("a@b.com", "ok-pass")
    assert token == "jwt:8:HS256"

    with pytest.raises(ValueError, match="Invalid credentials"):
        AuthService.login("a@b.com", "bad-pass")


def test_auth_issue_token_pair_and_helpers(monkeypatch):
    fake_user = SimpleNamespace(id=2, role="admin")
    calls = []

    def _encode(payload, key, algorithm):
        calls.append(payload)
        return f"token-{len(calls)}"

    monkeypatch.setattr("api.services.auth_service.jwt.encode", _encode)

    pair = AuthService.issue_token_pair(
        fake_user,
        access_delta=timedelta(minutes=1),
        refresh_delta=timedelta(minutes=2),
    )

    assert pair["access_token"] == "token-1"
    assert pair["refresh_token"] == "token-2"
    assert "role" in calls[0]
    assert "role" not in calls[1]

    received = {}
    monkeypatch.setattr(
        "api.services.auth_service.UserRepository.update_refresh_token",
        lambda user_id, token, exp: received.update({"user_id": user_id, "token": token, "exp": exp}),
    )
    AuthService.persist_refresh_token(4, "refresh-x", pair["refresh_token_exp"])
    assert received["user_id"] == 4
    assert received["token"] == "refresh-x"

    resp = AuthService.build_auth_response(fake_user, "a", "r")
    assert resp == {"access_token": "a", "refresh_token": "r", "user_role": "admin", "user_id": 2}


def test_auth_create_entity_pages_validates_and_creates(monkeypatch):
    entity = SimpleNamespace(id=77, name="Brand X")

    with pytest.raises(ValueError, match="Invalid page data"):
        AuthService.create_entity_pages(entity, [{"platform": "instagram"}])

    monkeypatch.setattr("api.services.auth_service.AuthService.create_page_uuid", lambda link: f"uuid:{link}")

    def _create(**kwargs):
        return SimpleNamespace(uuid=kwargs["uuid"], link=kwargs["link"], platform=kwargs["platform"])

    monkeypatch.setattr("api.services.auth_service.PageRepository.create", _create)

    pages = AuthService.create_entity_pages(
        entity,
        [{"platform": "instagram", "link": "https://example.com/p"}],
    )

    assert pages == [
        {
            "page_id": "uuid:https://example.com/p",
            "page_link": "https://example.com/p",
            "platform": "instagram",
        }
    ]
    assert AuthService.create_entity_pages(entity, []) is None


def test_page_service_create_page_and_interaction_stats(monkeypatch):
    page, err = PageService.create_page({"platform": " ", "link": "a", "entity_id": 1})
    assert page is None
    assert "Missing required fields" in err

    monkeypatch.setattr("api.services.page_service.create_page_uuid", lambda link: f"id-{link}")
    monkeypatch.setattr(
        "api.services.page_service.PageRepository.create",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    created_page, err = PageService.create_page(
        {"platform": " Instagram ", "link": " HTTPS://A.B/C ", "entity_id": 9}
    )

    assert err is None
    assert created_page.platform == "instagram"
    assert created_page.link == "https://a.b/c"
    assert created_page.name == "https://a.b/c"

    row = (
        uuid.uuid4(),
        "MyPage",
        "instagram",
        datetime(2026, 1, 20, tzinfo=timezone.utc),
        [[{"id": "p1", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 5}]],
    )
    monkeypatch.setattr("api.services.page_service.PageHistoryRepository.get_page_posts", lambda page_id: [row])

    stats = PageService.get_page_interaction_stats("page-id")
    ig_weights = {m["name"]: m["score"] for m in platform_metrics["instagram"]["metrics"]}
    expected_score = 10 * ig_weights["comments"] + 5 * ig_weights["likes"]
    assert stats[0]["post_id"] == "p1"
    assert stats[0]["score"] == pytest.approx(expected_score)


def test_page_service_delegates_and_applies_start_date_filter(monkeypatch):
    monkeypatch.setattr("api.services.page_service.PageRepository.delete", lambda page_id: f"deleted:{page_id}")
    monkeypatch.setattr("api.services.page_service.PageRepository.get_all", lambda: ["p1", "p2"])
    monkeypatch.setattr("api.services.page_service.PageRepository.get_by_platform", lambda platform: [platform])

    assert PageService.delete_page("id-1") == "deleted:id-1"
    assert PageService.get_all_pages() == ["p1", "p2"]
    assert PageService.get_pages_by_platform("instagram") == ["instagram"]

    row = (
        uuid.uuid4(),
        "MyPage",
        "instagram",
        datetime(2026, 1, 20, tzinfo=timezone.utc),
        [[
            {"id": "older", "datetime": "2026-01-09T00:00:00Z", "comments": 10, "likes": 5},
            {"id": "newer", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 5},
        ]],
    )
    monkeypatch.setattr(
        "api.services.page_service.parse_iso_date",
        lambda value: datetime(2026, 1, 10, tzinfo=timezone.utc),
    )
    monkeypatch.setattr("api.services.page_service.PageHistoryRepository.get_page_posts", lambda page_id: [row])
    stats = PageService.get_page_interaction_stats("page-id", start_date="2026-01-10")
    assert [item["post_id"] for item in stats] == ["newer"]


def test_page_service_start_date_string_works_without_type_error(monkeypatch):
    row = (
        uuid.uuid4(),
        "MyPage",
        "instagram",
        datetime(2026, 1, 20, tzinfo=timezone.utc),
        [[
            {"id": "older", "datetime": "2026-01-09T00:00:00Z", "comments": 1, "likes": 1},
            {"id": "newer", "datetime": "2026-01-12T00:00:00Z", "comments": 2, "likes": 3},
        ]],
    )
    monkeypatch.setattr("api.services.page_service.PageHistoryRepository.get_page_posts", lambda page_id: [row])

    stats = PageService.get_page_interaction_stats("page-id", start_date="2026-01-10")
    assert [item["post_id"] for item in stats] == ["newer"]


def test_post_service_delegates_to_repository(monkeypatch):
    monkeypatch.setattr("api.services.post_service.PostRepository.get_by_composite_key", lambda *a: ("one", a))
    monkeypatch.setattr("api.services.post_service.PostRepository.get_by_platform", lambda p: [p])
    monkeypatch.setattr("api.services.post_service.PostRepository.get_by_page", lambda pid, p=None: [pid, p])
    monkeypatch.setattr("api.services.post_service.PostRepository.get_by_entity", lambda eid, p=None: [eid, p])
    monkeypatch.setattr("api.services.post_service.PostRepository.get_post_history", lambda *a: [a])

    assert PostService.get_post("x", "instagram", "1")[0] == "one"
    assert PostService.get_posts_by_platform("x") == ["x"]
    assert PostService.get_posts_by_page("p", "x") == ["p", "x"]
    assert PostService.get_posts_by_entity(1) == [1, None]
    assert PostService.get_post_history("p", "x", "id") == [("p", "x", "id")]


def test_entity_service_refine_and_followers_history(monkeypatch):
    d1 = datetime(2026, 1, 1, tzinfo=timezone.utc).date()
    d3 = datetime(2026, 1, 3, tzinfo=timezone.utc).date()
    assert EntityService.refine_daily_followers([(d1, 100), (d3, 140)]) == [
        (d1, 100),
        (datetime(2026, 1, 2, tzinfo=timezone.utc).date(), 120),
        (d3, 140),
    ]

    rows = [
        SimpleNamespace(page_id="p1", platform="instagram", recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc), followers=10),
        SimpleNamespace(page_id="p1", platform="instagram", recorded_at=datetime(2026, 1, 3, tzinfo=timezone.utc), followers=20),
    ]
    monkeypatch.setattr(
        "api.services.entity_service.PageHistoryRepository.get_followers_history_by_entity",
        lambda self, entity_id: rows,
    )

    data = EntityService.get_entity_followers_history(1)
    assert len(data) == 3
    assert data[1]["followers"] == 15


def test_entity_refine_daily_followers_edge_fill_strategies():
    d1 = datetime(2026, 1, 1, tzinfo=timezone.utc).date()
    d2 = datetime(2026, 1, 2, tzinfo=timezone.utc).date()
    d3 = datetime(2026, 1, 3, tzinfo=timezone.utc).date()

    # Only right-side known value.
    assert EntityService.refine_daily_followers([(d1, None), (d3, 30)]) == [
        (d1, 30),
        (d2, 30),
        (d3, 30),
    ]
    # Only left-side known value.
    assert EntityService.refine_daily_followers([(d1, 20), (d3, None)]) == [
        (d1, 20),
        (d2, 20),
        (d3, 20),
    ]
    # No known values at all.
    assert EntityService.refine_daily_followers([(d1, 0), (d3, None)]) == [
        (d1, 0),
        (d2, 0),
        (d3, 0),
    ]


def test_entity_service_compare_and_posts_timeline(monkeypatch):
    comp_rows = [
        SimpleNamespace(entity_name="A", entity_id=1, platform="instagram", recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc), followers=30),
        SimpleNamespace(entity_name="A", entity_id=1, platform="instagram", recorded_at=datetime(2026, 1, 2, tzinfo=timezone.utc), followers=40),
    ]
    monkeypatch.setattr(
        "api.services.entity_service.PageHistoryRepository.get_entites_followers_competition",
        lambda ids: comp_rows,
    )
    compared = EntityService.compare_entities_followers([1])
    assert compared["A"]["entity_id"] == 1
    assert compared["A"]["records"][0]["followers"] == 30

    timeline_rows = [
        SimpleNamespace(
            platform="instagram",
            page_id="p1",
            page_name="Pg",
            posts_metrics=[
                {"id": "new", "datetime": "2026-01-15T10:00:00Z"},
                {"id": "old", "datetime": "2026-01-01T10:00:00Z"},
            ],
        )
    ]
    monkeypatch.setattr(
        "api.services.entity_service.PageHistoryRepository.get_entity_posts_new",
        lambda self, entity_id, date_limit, max_posts: timeline_rows,
    )
    result = EntityService.get_entity_posts_timeline(1, date_str="2026-01-10T00:00:00Z", max_posts=10)
    assert [p["id"] for p in result] == ["new"]


def test_entity_service_get_entity_likes_history_interpolates_and_handles_facebook(monkeypatch):
    rows = [
        SimpleNamespace(
            page_id="ig-page",
            platform="instagram",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-post-1", "likes": 10}],
        ),
        SimpleNamespace(
            page_id="ig-page",
            platform="instagram",
            recorded_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-post-1", "likes": 16}],
        ),
        SimpleNamespace(
            page_id="fb-page",
            platform="facebook",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "fb-post-1", "likes": 4}],
        ),
        SimpleNamespace(
            page_id="fb-page",
            platform="facebook",
            recorded_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "fb-post-1", "likes": 10}],
        ),
    ]

    captured = {}

    def _repo(self, entity_id, date_limit):
        captured["entity_id"] = entity_id
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entity_likes_development", _repo)

    data = EntityService.get_entity_likes_history(7, start_date="2026-01-01")

    assert captured["entity_id"] == 7
    assert captured["date_limit"].isoformat() == "2026-01-01"

    gains = {
        (item["page_id"], item["platform"], item["date"]): item["likes_gained"]
        for item in data
    }

    assert gains[("ig-page", "instagram", "2026-01-01")] == 0
    assert gains[("ig-page", "instagram", "2026-01-02")] == 3
    assert gains[("ig-page", "instagram", "2026-01-03")] == 3
    assert gains[("fb-page", "facebook", "2026-01-02")] == 6


def test_entity_service_compare_entities_likes_groups_by_entity(monkeypatch):
    rows = [
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-x",
            platform="x",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 5}],
        ),
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-x",
            platform="x",
            recorded_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 9}],
        ),
        SimpleNamespace(
            entity_name="B",
            entity_id=2,
            page_id="b-li",
            platform="linkedin",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "likes_count": 10}],
        ),
        SimpleNamespace(
            entity_name="B",
            entity_id=2,
            page_id="b-li",
            platform="linkedin",
            recorded_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "likes_count": 14}],
        ),
    ]

    captured = {}

    def _repo(self, entity_ids, date_limit):
        captured["entity_ids"] = entity_ids
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entities_likes_development", _repo)

    data = EntityService.compare_entities_likes([1, 2], start_date="2026-01-01")

    assert captured["entity_ids"] == [1, 2]
    assert captured["date_limit"].isoformat() == "2026-01-01"
    assert data["A"]["entity_id"] == 1
    assert data["B"]["entity_id"] == 2

    a_gains = {
        (item["page_id"], item["platform"], item["date"]): item["likes_gained"]
        for item in data["A"]["records"]
    }
    b_gains = {
        (item["page_id"], item["platform"], item["date"]): item["likes_gained"]
        for item in data["B"]["records"]
    }

    assert a_gains[("a-x", "x", "2026-01-02")] == 4
    assert b_gains[("b-li", "linkedin", "2026-01-02")] == 2
    assert b_gains[("b-li", "linkedin", "2026-01-03")] == 2


def test_entity_service_get_entity_likes_history_default_window_and_mixed_platform_mapping(monkeypatch):
    fixed_now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("api.services.entity_service.datetime", _FixedDateTime)

    rows = [
        # LinkedIn uses likes_count.
        SimpleNamespace(
            page_id="li-page",
            platform="linkedin",
            recorded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "likes_count": 100}],
        ),
        SimpleNamespace(
            page_id="li-page",
            platform="linkedin",
            recorded_at=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "likes_count": 130}],
        ),
        # TikTok uses favorites_count.
        SimpleNamespace(
            page_id="tt-page",
            platform="tiktok",
            recorded_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
            posts_metrics=[{"video_id": "tt-1", "favorites_count": 50}],
        ),
        SimpleNamespace(
            page_id="tt-page",
            platform="tiktok",
            recorded_at=datetime(2026, 3, 21, 8, 0, tzinfo=timezone.utc),
            posts_metrics=[{"video_id": "tt-1", "favorites_count": 70}],
        ),
        # X uses likes and should keep the latest same-day snapshot.
        SimpleNamespace(
            page_id="x-page",
            platform="x",
            recorded_at=datetime(2026, 3, 20, 9, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 5}],
        ),
        SimpleNamespace(
            page_id="x-page",
            platform="x",
            recorded_at=datetime(2026, 3, 20, 23, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 9}],
        ),
        SimpleNamespace(
            page_id="x-page",
            platform="x",
            recorded_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 14}],
        ),
        # Facebook supported in likes development.
        SimpleNamespace(
            page_id="fb-page",
            platform="facebook",
            recorded_at=datetime(2026, 3, 20, 7, 0, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "fb-1", "likes": 3}],
        ),
    ]

    captured = {}

    def _repo(self, entity_id, date_limit):
        captured["entity_id"] = entity_id
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entity_likes_development", _repo)

    data = EntityService.get_entity_likes_history(9)

    assert captured["entity_id"] == 9
    assert captured["date_limit"].isoformat() == "2026-03-13"
    assert data == sorted(data, key=lambda x: (x["date"], x["platform"], str(x["page_id"])))

    gains = {
        (item["page_id"], item["platform"], item["date"]): item["likes_gained"]
        for item in data
    }

    assert gains[("li-page", "linkedin", "2026-03-20")] == 0
    assert gains[("li-page", "linkedin", "2026-03-21")] == 15
    assert gains[("li-page", "linkedin", "2026-03-22")] == 15
    assert gains[("tt-page", "tiktok", "2026-03-21")] == 20
    assert gains[("x-page", "x", "2026-03-21")] == 5
    assert gains[("fb-page", "facebook", "2026-03-20")] == 0


def test_entity_service_compare_entities_likes_default_window_ignores_invalid_entities(monkeypatch):
    fixed_now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("api.services.entity_service.datetime", _FixedDateTime)

    rows = [
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-ig",
            platform="instagram",
            recorded_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-1", "likes": 10}],
        ),
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-ig",
            platform="instagram",
            recorded_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-1", "likes": 15}],
        ),
        # Should be ignored because entity_name is missing.
        SimpleNamespace(
            entity_name=None,
            entity_id=2,
            page_id="no-name",
            platform="x",
            recorded_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "likes": 100}],
        ),
        # Should be ignored because posts are empty and produce no records.
        SimpleNamespace(
            entity_name="B",
            entity_id=2,
            page_id="b-li",
            platform="linkedin",
            recorded_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
            posts_metrics=[],
        ),
    ]

    captured = {}

    def _repo(self, entity_ids, date_limit):
        captured["entity_ids"] = entity_ids
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entities_likes_development", _repo)

    data = EntityService.compare_entities_likes([1, 2])

    assert captured["entity_ids"] == [1, 2]
    assert captured["date_limit"].isoformat() == "2026-03-13"
    assert list(data.keys()) == ["A"]
    assert data["A"]["entity_id"] == 1
    assert data["A"]["records"][1]["likes_gained"] == 5


def test_entity_service_get_entity_comments_history_interpolates_and_handles_facebook(monkeypatch):
    rows = [
        SimpleNamespace(
            page_id="ig-page",
            platform="instagram",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-post-1", "comments": 10}],
        ),
        SimpleNamespace(
            page_id="ig-page",
            platform="instagram",
            recorded_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-post-1", "comments": 16}],
        ),
        SimpleNamespace(
            page_id="fb-page",
            platform="facebook",
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "fb-post-1", "num_comments": 4}],
        ),
        SimpleNamespace(
            page_id="fb-page",
            platform="facebook",
            recorded_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "fb-post-1", "num_comments": 10}],
        ),
    ]

    captured = {}

    def _repo(self, entity_id, date_limit):
        captured["entity_id"] = entity_id
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entity_comments_development", _repo)

    data = EntityService.get_entity_comments_history(7, start_date="2026-01-01")

    assert captured["entity_id"] == 7
    assert captured["date_limit"].isoformat() == "2026-01-01"

    gains = {
        (item["page_id"], item["platform"], item["date"]): item["comments_gained"]
        for item in data
    }

    assert gains[("ig-page", "instagram", "2026-01-01")] == 0
    assert gains[("ig-page", "instagram", "2026-01-02")] == 3
    assert gains[("ig-page", "instagram", "2026-01-03")] == 3
    assert gains[("fb-page", "facebook", "2026-01-02")] == 6


def test_entity_service_compare_entities_comments_default_window_and_mapping(monkeypatch):
    fixed_now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("api.services.entity_service.datetime", _FixedDateTime)

    rows = [
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-x",
            platform="x",
            recorded_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "replies": 20}],
        ),
        SimpleNamespace(
            entity_name="A",
            entity_id=1,
            page_id="a-x",
            platform="x",
            recorded_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "x-1", "replies": 29}],
        ),
        SimpleNamespace(
            entity_name="B",
            entity_id=2,
            page_id="b-li",
            platform="linkedin",
            recorded_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "comments_count": 10}],
        ),
        SimpleNamespace(
            entity_name="B",
            entity_id=2,
            page_id="b-li",
            platform="linkedin",
            recorded_at=datetime(2026, 3, 22, tzinfo=timezone.utc),
            posts_metrics=[{"post_id": "li-1", "comments_count": 16}],
        ),
        # Should be ignored because entity_name is missing.
        SimpleNamespace(
            entity_name=None,
            entity_id=3,
            page_id="skip",
            platform="instagram",
            recorded_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
            posts_metrics=[{"id": "ig-1", "comments": 12}],
        ),
    ]

    captured = {}

    def _repo(self, entity_ids, date_limit):
        captured["entity_ids"] = entity_ids
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entities_comments_development", _repo)

    data = EntityService.compare_entities_comments([1, 2, 3])

    assert captured["entity_ids"] == [1, 2, 3]
    assert captured["date_limit"].isoformat() == "2026-03-13"
    assert set(data.keys()) == {"A", "B"}

    a_gains = {
        (item["page_id"], item["platform"], item["date"]): item["comments_gained"]
        for item in data["A"]["records"]
    }
    b_gains = {
        (item["page_id"], item["platform"], item["date"]): item["comments_gained"]
        for item in data["B"]["records"]
    }

    assert a_gains[("a-x", "x", "2026-03-21")] == 9
    assert b_gains[("b-li", "linkedin", "2026-03-21")] == 3
    assert b_gains[("b-li", "linkedin", "2026-03-22")] == 3


def test_entity_service_delegates_and_timeline_youtube_branch(monkeypatch):
    monkeypatch.setattr("api.services.entity_service.EntityRepository.create", lambda name, type_: SimpleNamespace(id=5, name=name, type=type_))
    monkeypatch.setattr("api.services.entity_service.EntityCategoryRepository.add", lambda entity_id, category_id: {"entity_id": entity_id, "category_id": category_id})
    monkeypatch.setattr("api.services.entity_service.EntityRepository.get_all", lambda: ["e1"])
    monkeypatch.setattr("api.services.entity_service.EntityRepository.get_who_has_history", lambda: ["e-history"])
    monkeypatch.setattr("api.services.entity_service.EntityCategoryRepository.delete_by_entity", lambda entity_id: None)
    monkeypatch.setattr("api.services.entity_service.EntityRepository.delete", lambda entity_id: entity_id == 99)
    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entity_info_from_history", lambda entity_id: {"entity_id": entity_id})
    monkeypatch.setattr("api.services.entity_service.EntityRepository.change_to_scrape", lambda entity_id, value: {"entity_id": entity_id, "to_scrape": value})

    entity, entity_category = EntityService.create_entity("Acme", "brand", 3)
    assert entity.id == 5
    assert entity_category == {"entity_id": 5, "category_id": 3}
    assert EntityService.get_all_entities() == ["e1"]
    assert EntityService.get_existing_entities() == ["e-history"]
    assert EntityService.delete_entity(99) is True
    assert EntityService.get_entity_profile_card(7) == {"entity_id": 7}
    assert EntityService.mark_entity_to_scrape(11) == {"entity_id": 11, "to_scrape": True}

    captured = {}

    def _get_entity_posts_new(self, entity_id, date_limit, max_posts):
        captured["entity_id"] = entity_id
        captured["date_limit"] = date_limit
        captured["max_posts"] = max_posts
        return [
            SimpleNamespace(
                platform="youtube",
                page_id="yt1",
                page_name="YT Page",
                posts_metrics=[{"video_id": "v1", "posted_time": "2 day ago"}],
            )
        ]

    monkeypatch.setattr("api.services.entity_service.PageHistoryRepository.get_entity_posts_new", _get_entity_posts_new)
    monkeypatch.setattr(
        "api.services.entity_service.parse_relative_time",
        lambda value: datetime(2026, 1, 20, tzinfo=timezone.utc),
    )

    timeline = EntityService.get_entity_posts_timeline(1, max_posts=0)
    assert captured["max_posts"] == 10000
    assert timeline[0]["video_id"] == "v1"
    assert timeline[0]["platform"] == "youtube"


def test_entity_timeline_skips_unsupported_platform_and_bad_youtube_relative_time(monkeypatch):
    rows = [
        SimpleNamespace(
            platform="unsupported",
            page_id="p1",
            page_name="Pg",
            posts_metrics=[{"id": "x", "datetime": "2026-01-15T10:00:00Z"}],
        ),
        SimpleNamespace(
            platform="youtube",
            page_id="yt1",
            page_name="YT",
            posts_metrics=[{"video_id": "v1", "posted_time": "not-relative"}],
        ),
    ]
    monkeypatch.setattr(
        "api.services.entity_service.PageHistoryRepository.get_entity_posts_new",
        lambda self, entity_id, date_limit, max_posts: rows,
    )
    monkeypatch.setattr("api.services.entity_service.parse_relative_time", lambda value: None)

    result = EntityService.get_entity_posts_timeline(1, date_str="2026-01-10T00:00:00Z", max_posts=10)
    assert result == []


def test_entity_top_posts_computes_gains_ranks_and_counters(monkeypatch):
    rows = [
        SimpleNamespace(
            platform="instagram",
            recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
            posts_metrics=[[{"id": "a", "datetime": "2026-01-19T00:00:00Z", "comments": 2, "likes": 5}]],
        ),
        SimpleNamespace(
            platform="instagram",
            recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
            posts_metrics=[[{"id": "a", "datetime": "2026-01-20T00:00:00Z", "comments": 6, "likes": 9}, {"oops": 1}]],
        ),
    ]
    monkeypatch.setattr("api.services.entity_service.EntityRepository.get_entity_posts_metrics", lambda entity_id, date_limit: rows)

    day_gains, posts_num, skipped = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)
    assert day_gains["day"] == "2026-01-20"
    assert day_gains["posts"][0]["gained_comments"] == 4
    assert day_gains["posts"][0]["rank"] == 1
    assert posts_num == 3
    assert skipped == 1


def test_influence_service_ranking_and_interaction_summary(monkeypatch):
    ranking_rows = [
        SimpleNamespace(
            entity_id=1,
            entity_name="Entity A",
            category="cat",
            root_category="root",
            platform="instagram",
            recorded_at=datetime(2026, 1, 20, 10, tzinfo=timezone.utc),
            page_id="pg1",
            page_name="Page A",
            page_url="https://example.com",
            profile_url="https://img",
            posts_metrics=[{"comments": 10, "likes": 20}],
        )
    ]
    followers_rows = [SimpleNamespace(page_id="pg1", current_followers=500, prev_followers=450)]
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_all_entities_posts", lambda date_limit: ranking_rows)
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_entities_followers_snapshot", lambda date_limit: followers_rows)

    ranked = InfluenceHistoryService.entities_ranking()
    assert ranked[0]["entity_name"] == "Entity A"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["total_followers"] == 500

    interaction_rows = [
        SimpleNamespace(
            platform="instagram",
            recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
            posts=[[{"id": "p1", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 20}]],
        ),
        SimpleNamespace(
            platform="instagram",
            recorded_at=datetime(2026, 1, 21, tzinfo=timezone.utc),
            posts=[[{"id": "p1", "datetime": "2026-01-21T00:00:00Z", "comments": 13, "likes": 26}]],
        ),
    ]
    monkeypatch.setattr(
        "api.services.influence_history_service.PageHistoryRepository.get_entity_posts__old",
        lambda entity_id: interaction_rows,
    )
    summary = InfluenceHistoryService.get_entity_interaction_stats(1)
    assert summary[-1]["date"] == "2026-01-21"
    assert summary[-1]["total_score"] > 0


def test_influence_service_delegates_and_competitors_stats(monkeypatch):
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_after_time", lambda hour: [hour])
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_all_entities_ranking", lambda: ["ranked"])

    monkeypatch.setattr("api.services.influence_history_service.parse_iso_date", lambda value: datetime(2026, 1, 15).date())

    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_today_all", lambda self: ["today"])
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_page_data_today", lambda self, page_id: [page_id])
    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_platform_history", lambda self, platform: [platform])
    monkeypatch.setattr(
        "api.services.influence_history_service.PageHistoryRepository.get_entity_data_by_date",
        lambda self, entity_id, target_date: {"entity_id": entity_id, "target_date": target_date.isoformat()},
    )

    assert InfluenceHistoryService.get_after_time(2) == [2]
    assert InfluenceHistoryService.get_today_pages_history() == ["today"]
    assert InfluenceHistoryService.get_page_history_today("pg") == ["pg"]
    assert InfluenceHistoryService.get_platform_history("instagram") == ["instagram"]
    assert InfluenceHistoryService.get_entity_history(7, "2026-01-15") == {
        "entity_id": 7,
        "target_date": "2026-01-15",
    }
    assert InfluenceHistoryService.get_entities_ranking() == ["ranked"]

    class _Row:
        def __init__(self, page_id, platform, entity_id, posts_metrics):
            self.page_id = page_id
            self.platform = platform
            self.entity_id = entity_id
            self.posts_metrics = posts_metrics

    rows = [
        _Row(
            "pg1",
            "instagram",
            10,
            [[{"id": "p1", "datetime": "2026-01-20T00:00:00Z", "comments": 6, "likes": 4}]],
        )
    ]

    captured = {}

    monkeypatch.setattr(
        "api.services.influence_history_service.PageHistoryRepository.get_entity_posts_new",
        lambda self, entity_id, date_limit, max_posts: captured.update(
            {"entity_id": entity_id, "date_limit": date_limit, "max_posts": max_posts}
        )
        or rows,
    )

    stats = InfluenceHistoryService.get_competitors_interaction_stats([10], start_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert captured["entity_id"] == 10
    assert captured["date_limit"].isoformat() == "2026-01-01"
    assert captured["max_posts"] == 10000
    assert len(stats) == 1
    assert stats[0]["platform"] == "instagram"
    assert stats[0]["entity_id"] == 10


def test_influence_competitors_stats_skips_invalid_rows_and_respects_start_date(monkeypatch):
    rows = [
        SimpleNamespace(
            page_id="pg1",
            platform="instagram",
            entity_id=10,
            posts_metrics=[[{"id": "old", "datetime": "2025-12-31T00:00:00Z", "comments": 1, "likes": 1}]],
        ),
        SimpleNamespace(
            page_id="pg1",
            platform="instagram",
            entity_id=10,
            posts_metrics=[[{"id": "ok", "datetime": "2026-01-02T00:00:00Z", "comments": "6", "likes": "4"}, "bad-item"]],
        ),
        SimpleNamespace(
            page_id="pg2",
            platform="unsupported",
            entity_id=10,
            posts_metrics=[[{"id": "x", "datetime": "2026-01-03T00:00:00Z"}]],
        ),
        SimpleNamespace(
            page_id="pg3",
            platform="instagram",
            entity_id=10,
            posts_metrics="not-a-list",
        ),
    ]

    captured = {}
    monkeypatch.setattr(
        "api.services.influence_history_service.PageHistoryRepository.get_entity_posts_new",
        lambda self, entity_id, date_limit, max_posts: captured.update(
            {"entity_id": entity_id, "date_limit": date_limit, "max_posts": max_posts}
        )
        or rows,
    )

    stats = InfluenceHistoryService.get_competitors_interaction_stats(
        [10],
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert captured["max_posts"] == 10000
    assert captured["date_limit"].isoformat() == "2026-01-01"
    assert [s["post_id"] for s in stats] == ["ok"]


def test_influence_interactions_ranking_default_window_and_weighted_scores(monkeypatch):
    fixed_now = datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("api.services.influence_history_service.datetime", _FixedDateTime)

    captured = {}
    rows = [
        {
            "entity_id": 1,
            "entity_name": "A Corp",
            "category": "auto",
            "root_category": "business",
            "platform": "instagram",
            "posts_count": 2,
            "total_likes": 100,
            "total_comments": 10,
            "total_shares": 0,
            "total_views": 0,
        },
        {
            "entity_id": 1,
            "entity_name": "A Corp",
            "category": "auto",
            "root_category": "business",
            "platform": "x",
            "posts_count": 1,
            "total_likes": 20,
            "total_comments": 8,
            "total_shares": 6,
            "total_views": 30,
        },
        {
            "entity_id": 2,
            "entity_name": "B Corp",
            "category": "tech",
            "root_category": "business",
            "platform": "linkedin",
            "posts_count": 3,
            "total_likes": 50,
            "total_comments": 20,
            "total_shares": 0,
            "total_views": 0,
        },
        # Unsupported for scoring here because platform_metrics has no youtube.
        {
            "entity_id": 2,
            "entity_name": "B Corp",
            "category": "tech",
            "root_category": "business",
            "platform": "youtube",
            "posts_count": 9,
            "total_likes": 999,
            "total_comments": 999,
            "total_shares": 999,
            "total_views": 999,
        },
    ]

    def _repo(date_limit):
        captured["date_limit"] = date_limit
        return rows

    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_companies_interactions_summary", _repo)

    ranking = InfluenceHistoryService.get_interactions_ranking()

    assert captured["date_limit"].isoformat() == "2026-03-13"
    assert len(ranking) == 2
    assert ranking[0]["entity_name"] == "A Corp"
    assert ranking[0]["category"] == "auto"
    assert ranking[0]["root_category"] == "business"
    assert ranking[0]["rank"] == 1
    assert ranking[0]["total_posts"] == 3
    ig_weights = {m["name"]: m["score"] for m in platform_metrics["instagram"]["metrics"]}
    x_weights = {m["name"]: m["score"] for m in platform_metrics["x"]["metrics"]}
    li_weights = {m["name"]: m["score"] for m in platform_metrics["linkedin"]["metrics"]}

    expected_a_score = (
        100 * ig_weights["likes"]
        + 10 * ig_weights["comments"]
        + 20 * x_weights["likes"]
        + 8 * x_weights["replies"]
        + 6 * x_weights["reposts"]
    )
    expected_b_score = 50 * li_weights["likes_count"] + 20 * li_weights["comments_count"]

    assert ranking[0]["total_score"] == pytest.approx(expected_a_score)
    assert "instagram" in ranking[0]["platforms"]
    assert "x" in ranking[0]["platforms"]

    assert ranking[1]["entity_name"] == "B Corp"
    assert ranking[1]["category"] == "tech"
    assert ranking[1]["root_category"] == "business"
    assert ranking[1]["rank"] == 2
    assert ranking[1]["total_score"] == pytest.approx(expected_b_score)
    assert "youtube" not in ranking[1]["platforms"]


def test_influence_interactions_ranking_start_date_and_empty_result(monkeypatch):
    captured = {}

    def _repo(date_limit):
        captured["date_limit"] = date_limit
        return []

    monkeypatch.setattr("api.services.influence_history_service.PageHistoryRepository.get_companies_interactions_summary", _repo)

    ranking = InfluenceHistoryService.get_interactions_ranking(start_date="2026-01-01")

    assert captured["date_limit"].isoformat() == "2026-01-01"
    assert ranking == []
    