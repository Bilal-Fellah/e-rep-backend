import pytest

from api.services.scrape_validation_service import (
    RECOVERY_SOURCE_PRIORITY,
    ScrapeValidationError,
    ScrapeValidationService,
    recommend_recovery_sources,
    validate_posts_snapshot,
    validate_profile_snapshot,
)


# ── Profile snapshots ────────────────────────────────────────────────────

def test_profile_complete_when_all_tracked_fields_present():
    data = {"followers": 1000, "biography": "hello", "profile_image_link": "http://x/y.png"}
    result = validate_profile_snapshot("instagram", data)
    assert result.status == "complete"
    assert result.missing_required == []
    assert result.missing_optional == []
    assert result.is_usable


def test_profile_partial_when_only_followers_missing():
    data = {"biography": "hello", "profile_image_link": "http://x/y.png"}
    result = validate_profile_snapshot("instagram", data)
    assert result.status == "partial"
    assert result.missing_required == ["followers"]
    assert result.is_usable


def test_profile_failed_when_nothing_came_back():
    result = validate_profile_snapshot("instagram", {})
    assert result.status == "failed"
    assert result.missing_required == ["followers"]
    assert set(result.missing_optional) == {"biography", "profile_image"}
    assert not result.is_usable


def test_profile_failed_on_none_data():
    result = validate_profile_snapshot("instagram", None)
    assert result.status == "failed"


def test_facebook_bio_and_image_are_not_tracked_so_never_count_as_missing():
    # Facebook pages_history rows don't carry a bio/profile-image key at
    # all (see PageHistoryRepository._description_case/_profile_url_case),
    # so a snapshot with only page_followers is COMPLETE for facebook, not
    # partial — the platform simply doesn't track those two fields.
    result = validate_profile_snapshot("facebook", {"page_followers": 500})
    assert result.status == "complete"
    assert result.missing_optional == []


def test_youtube_uses_subscribers_key_for_followers():
    result = validate_profile_snapshot("youtube", {"subscribers": 42})
    assert "followers" not in result.missing_required


def test_unknown_platform_raises():
    with pytest.raises(ScrapeValidationError):
        validate_profile_snapshot("myspace", {})


def test_service_wrapper_matches_module_function():
    data = {"followers": 10}
    assert ScrapeValidationService.validate_profile_snapshot("x", data).status == (
        validate_profile_snapshot("x", data).status
    )


# ── Posts snapshots ──────────────────────────────────────────────────────

def test_posts_complete_when_every_post_has_required_metrics():
    posts = [{"id": "1", "likes": 5, "comments": 2}, {"id": "2", "likes": 0, "comments": 0}]
    result = validate_posts_snapshot("instagram", posts)
    assert result.status == "complete"


def test_posts_partial_when_some_posts_missing_a_metric():
    posts = [{"id": "1", "likes": 5, "comments": 2}, {"id": "2", "likes": None, "comments": 3}]
    result = validate_posts_snapshot("instagram", posts)
    assert result.status == "partial"
    assert result.missing_required == ["likes"]
    assert result.detail["missing_counts"]["likes"] == 1


def test_posts_failed_when_every_post_missing_every_required_metric():
    posts = [{"id": "1", "likes": None, "comments": None}, {"id": "2", "likes": None, "comments": None}]
    result = validate_posts_snapshot("instagram", posts)
    assert result.status == "failed"


def test_posts_failed_when_empty_and_posts_were_expected():
    result = validate_posts_snapshot("instagram", [], min_expected_posts=1)
    assert result.status == "failed"


def test_posts_optional_shares_only_checked_when_platform_tracks_it():
    # Instagram doesn't track shares at all in POSTS_FIELD_MAP -> never
    # reported as missing. TikTok does -> missing shares shows up.
    ig = validate_posts_snapshot("instagram", [{"id": "1", "likes": 1, "comments": 1}])
    assert ig.missing_optional == []

    tiktok = validate_posts_snapshot(
        "tiktok", [{"video_id": "1", "favorites_count": 1, "commentcount": 1, "share_count": None}]
    )
    assert tiktok.missing_optional == ["shares"]
    assert tiktok.status == "partial"


def test_facebook_flat_posts_use_num_comments_and_num_shares_keys():
    posts = [{"post_id": "1", "likes": 3, "num_comments": 1, "num_shares": 0}]
    result = validate_posts_snapshot("facebook", posts)
    assert result.status == "complete"


# ── Cheap-recovery recommendation ───────────────────────────────────────
# The brief: "in case of partial success ... we need to know how we can
# get the missing data in a reasonably cheap method." This is the part of
# the validation check that answers that directly.

def test_recommend_recovery_sources_is_cheapest_first_and_platform_specific():
    assert recommend_recovery_sources("instagram", "profile") == ["own_scraper", "apify"]
    assert recommend_recovery_sources("facebook", "profile") == ["apify"]


def test_recommend_recovery_sources_defaults_to_apify_for_unknown_platform():
    # A platform this table hasn't been taught about yet still gets a
    # usable answer rather than an empty/undefined recommendation.
    assert recommend_recovery_sources("myspace", "profile") == ["apify"]


def test_recommend_recovery_sources_returns_a_copy_not_the_live_table():
    result = recommend_recovery_sources("instagram", "profile")
    result.append("mutated")
    assert RECOVERY_SOURCE_PRIORITY["profile"]["instagram"] == ["own_scraper", "apify"]


def test_complete_profile_snapshot_has_no_recommended_sources():
    data = {"followers": 1, "biography": "b", "profile_image_link": "u"}
    result = validate_profile_snapshot("instagram", data)
    assert result.status == "complete"
    assert result.recommended_sources == []


def test_partial_profile_snapshot_recommends_cheapest_source_first():
    result = validate_profile_snapshot("instagram", {"biography": "b", "profile_image_link": "u"})
    assert result.status == "partial"
    assert result.recommended_sources == ["own_scraper", "apify"]


def test_failed_profile_snapshot_still_recommends_a_recovery_path():
    result = validate_profile_snapshot("facebook", {})
    assert result.status == "failed"
    assert result.recommended_sources == ["apify"]


def test_partial_posts_snapshot_recommends_recovery_sources():
    posts = [{"id": "1", "likes": None, "comments": 2}]
    result = validate_posts_snapshot("instagram", posts)
    assert result.status == "partial"
    assert result.recommended_sources == ["own_scraper", "apify"]


def test_empty_posts_snapshot_recommends_recovery_sources_too():
    result = validate_posts_snapshot("tiktok", [], min_expected_posts=1)
    assert result.status == "failed"
    assert result.recommended_sources == ["apify"]


def test_service_wrapper_exposes_recommendation_too():
    assert ScrapeValidationService.recommend_recovery_sources("instagram") == ["own_scraper", "apify"]
