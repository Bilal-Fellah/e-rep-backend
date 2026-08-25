# Tests for the profile-info flow added to ScrapingService (see
# api/docs/scraping_profiles.md) -- the counterpart to the existing
# comment-flow tests, covering fetch_profiles_for_scraping,
# validate_profile_data, and insert_profile_batch.
import uuid

import pytest

from api.services.scraping_service import ScrapingService


# ── validate_profile_data (pure logic) ──────────────────────────────────

def test_validate_profile_data_requires_routing_fields():
    ok, err = ScrapingService.validate_profile_data(
        {"platform": "instagram", "account_id": "a1"}
    )
    assert ok is False
    assert "page_id" in err


def test_validate_profile_data_rejects_unsupported_platform():
    ok, err = ScrapingService.validate_profile_data(
        {"page_id": "p1", "platform": "tiktok", "account_id": "a1"}
    )
    assert ok is False
    assert "tiktok" in err


def test_validate_profile_data_accepts_instagram():
    ok, err = ScrapingService.validate_profile_data(
        {"page_id": "p1", "platform": "instagram", "account_id": "a1", "followers": 100}
    )
    assert ok is True
    assert err == ""


# ── fetch_profiles_for_scraping / insert_profile_batch (real DB) ───────

def _make_page(db_session, platform="instagram", to_scrape=True):
    from api.models.entity_model import Entity
    from api.models.page_model import Page

    entity = Entity(name=f"Test {uuid.uuid4()}", type="company", to_scrape=to_scrape)
    db_session.add(entity)
    db_session.flush()
    page = Page(
        name="p", link=f"https://instagram.com/{uuid.uuid4()}", platform=platform, entity_id=entity.id
    )
    db_session.add(page)
    db_session.flush()
    return page


def test_fetch_profiles_for_scraping_rejects_unsupported_platform(db_session):
    with pytest.raises(ValueError, match="tiktok"):
        ScrapingService.fetch_profiles_for_scraping(platform="tiktok")


def test_fetch_profiles_for_scraping_only_returns_active_pages(db_session):
    active = _make_page(db_session, to_scrape=True)
    _make_page(db_session, to_scrape=False)  # inactive entity, must be excluded

    result = ScrapingService.fetch_profiles_for_scraping(platform="instagram")

    page_ids = {p["page_id"] for p in result["profiles"]}
    assert str(active.uuid) in page_ids
    assert result["count"] == len(page_ids)
    entry = next(p for p in result["profiles"] if p["page_id"] == str(active.uuid))
    assert entry["account_id"] == str(active.uuid)  # account_id == page_id, see model docstring
    assert entry["url"] == active.link
    assert result["session_id"]


def test_fetch_profiles_for_scraping_excludes_pages_already_done_today(db_session):
    from api.repositories.scraping_profile_result_repository import ScrapingProfileResultRepository

    page = _make_page(db_session)
    ScrapingProfileResultRepository.record(
        page_id=str(page.uuid), platform="instagram", account_id=str(page.uuid),
        profile_inserted=True, scraping_session_id=None, commit=False,
    )
    db_session.flush()

    result = ScrapingService.fetch_profiles_for_scraping(platform="instagram")

    assert str(page.uuid) not in {p["page_id"] for p in result["profiles"]}
    assert result["total_available"] >= 1  # still counted as active, just not "pending"


def test_insert_profile_batch_writes_pages_history_with_own_scraper_source(db_session):
    from api.repositories.page_history_repository import PageHistoryRepository

    page = _make_page(db_session)
    profiles = [
        {
            "page_id": str(page.uuid),
            "platform": "instagram",
            "account_id": str(page.uuid),
            "followers": 12345,
            "biography": "hello",
            "profile_image_link": "https://example/img.jpg",
            "posts": [],
        }
    ]

    result = ScrapingService.insert_profile_batch(profiles, session_id=None, profile_results=None)

    assert result["inserted"] == 1
    assert result["total"] == 1

    histories = PageHistoryRepository.get_page_data_today(page.uuid)
    assert len(histories) == 1
    row = histories[0]
    assert row.source == "own_scraper"
    assert row.data["followers"] == 12345
    assert row.data["biography"] == "hello"
    assert "page_id" not in row.data  # routing keys stripped, not stored twice


def test_insert_profile_batch_rejects_whole_batch_on_first_invalid_entry(db_session):
    profiles = [
        {"page_id": "p1", "platform": "instagram", "account_id": "a1", "followers": 1},
        {"page_id": "p2", "platform": "instagram"},  # missing account_id
    ]
    with pytest.raises(ValueError, match="index 1"):
        ScrapingService.insert_profile_batch(profiles, session_id=None)


def test_insert_profile_batch_records_unscrapeable_accounts_without_inserting(db_session):
    from api.repositories.scraping_profile_result_repository import ScrapingProfileResultRepository

    page = _make_page(db_session)
    profile_results = [
        {"page_id": str(page.uuid), "platform": "instagram", "account_id": str(page.uuid)}
    ]

    result = ScrapingService.insert_profile_batch([], session_id=None, profile_results=profile_results)

    assert result["inserted"] == 0
    stored = ScrapingProfileResultRepository.get_by_page_and_session(
        str(page.uuid), "instagram", None
    )
    assert stored is not None
    assert stored.profile_inserted is False
