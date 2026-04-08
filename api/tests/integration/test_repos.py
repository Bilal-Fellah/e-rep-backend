from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_repository import PageRepository
from api.repositories.post_repository import PostRepository
from api.repositories.user_repository import UserRepository


def test_user_repository_update_refresh_token_success_and_missing(monkeypatch):
    fake_user = SimpleNamespace(refresh_token=None, refresh_token_exp=None)
    commits = {"count": 0}

    fake_session = SimpleNamespace(
        get=lambda model, user_id: fake_user if user_id == 1 else None,
        commit=lambda: commits.update({"count": commits["count"] + 1}),
    )
    monkeypatch.setattr("api.repositories.user_repository.db", SimpleNamespace(session=fake_session))

    exp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    UserRepository.update_refresh_token(1, token="r1", exp=exp)
    assert fake_user.refresh_token == "r1"
    assert fake_user.refresh_token_exp == exp
    assert commits["count"] == 1

    with pytest.raises(ValueError, match="User not found"):
        UserRepository.update_refresh_token(999, token="x", exp=exp)


def test_page_repository_delete_and_get_by_platform(monkeypatch):
    deleted = {"obj": None, "commit": 0}
    page = SimpleNamespace(id="pg1")

    class _Query:
        @staticmethod
        def get(page_id):
            return page if page_id == "pg1" else None

    fake_page = SimpleNamespace(query=_Query, platform="platform-col")
    monkeypatch.setattr("api.repositories.page_repository.Page", fake_page)
    monkeypatch.setattr(
        "api.repositories.page_repository.select",
        lambda _model: SimpleNamespace(where=lambda _expr: "fake-stmt"),
    )

    fake_session = SimpleNamespace(
        delete=lambda obj: deleted.update({"obj": obj}),
        commit=lambda: deleted.update({"commit": deleted["commit"] + 1}),
        scalars=lambda stmt: SimpleNamespace(all=lambda: ["ig-page"]),
    )
    monkeypatch.setattr("api.repositories.page_repository.db", SimpleNamespace(session=fake_session))

    assert PageRepository.get_by_platform("instagram") == ["ig-page"]
    assert PageRepository.delete("missing") is False
    assert PageRepository.delete("pg1") is True
    assert deleted["obj"] is page
    assert deleted["commit"] == 1


def test_post_repository_get_by_page_applies_optional_platform(monkeypatch):
    calls = []

    class _QueryChain:
        def filter_by(self, **kwargs):
            calls.append(("filter_by", kwargs))
            return self

        def order_by(self, *_args, **_kwargs):
            calls.append(("order_by", None))
            return self

        def all(self):
            return ["ok"]

    post_mv = SimpleNamespace(query=_QueryChain(), created_at=SimpleNamespace(desc=lambda: "desc"))
    monkeypatch.setattr("api.repositories.post_repository.PostMV", post_mv)

    assert PostRepository.get_by_page("p1") == ["ok"]
    assert ("filter_by", {"page_id": "p1"}) in calls

    calls.clear()
    assert PostRepository.get_by_page("p1", "instagram") == ["ok"]
    assert ("filter_by", {"platform": "instagram"}) in calls


def test_entity_repository_change_to_scrape_and_delete(monkeypatch):
    entity = SimpleNamespace(to_scrape=False)
    deleted = {"obj": None, "commit": 0}

    class _Query:
        @staticmethod
        def get(entity_id):
            return entity if entity_id == 1 else None

    monkeypatch.setattr("api.repositories.entity_repository.Entity", SimpleNamespace(query=_Query))

    fake_session = SimpleNamespace(
        delete=lambda obj: deleted.update({"obj": obj}),
        commit=lambda: deleted.update({"commit": deleted["commit"] + 1}),
    )
    monkeypatch.setattr("api.repositories.entity_repository.db", SimpleNamespace(session=fake_session))

    assert EntityRepository.change_to_scrape(1, True) is entity
    assert entity.to_scrape is True
    assert EntityRepository.change_to_scrape(2, True) is None
    assert EntityRepository.delete(2) is False
    assert EntityRepository.delete(1) is True
    assert deleted["obj"] is entity


def test_category_and_entity_category_create_delete(monkeypatch):
    ops = {"added": [], "deleted": [], "commits": 0}

    fake_session = SimpleNamespace(
        add=lambda obj: ops["added"].append(obj),
        delete=lambda obj: ops["deleted"].append(obj),
        commit=lambda: ops.update({"commits": ops["commits"] + 1}),
    )

    monkeypatch.setattr("api.repositories.category_repository.db", SimpleNamespace(session=fake_session))
    monkeypatch.setattr("api.repositories.entity_category_repository.db", SimpleNamespace(session=fake_session))

    class _Category:
        query = SimpleNamespace(get=lambda category_id: SimpleNamespace(id=category_id) if category_id == 1 else None)

        def __init__(self, name, parent_id=None):
            self.name = name
            self.parent_id = parent_id

    class _EntityCategory:
        query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: SimpleNamespace(**kwargs) if kwargs.get("entity_id") == 7 else None)
        )

        def __init__(self, entity_id, category_id):
            self.entity_id = entity_id
            self.category_id = category_id

    monkeypatch.setattr("api.repositories.category_repository.Category", _Category)
    monkeypatch.setattr("api.repositories.entity_category_repository.EntityCategory", _EntityCategory)

    created_category = CategoryRepository.create("sports", parent_id=1)
    assert created_category.name == "sports"
    assert created_category.parent_id == 1

    created_link = EntityCategoryRepository.add(7, 3)
    assert created_link.entity_id == 7
    assert created_link.category_id == 3

    assert EntityCategoryRepository.delete_by_entity(7) is True
    assert EntityCategoryRepository.delete_by_entity(999) is False