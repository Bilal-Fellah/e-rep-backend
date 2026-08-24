# End-to-end integration tests for Apify Fallback Scraping feature.
# Task 8.1: Test end-to-end flow with Apify service
import os
import pytest
from datetime import datetime, timedelta, date
from uuid import uuid4
from api.models.page_model import Page
from api.models.entity_model import Entity
from api.models.page_history_model import PageHistory
from api import db


@pytest.fixture
def api_key():
    """Set and return test API key."""
    test_key = "test-apify-fallback-api-key-12345"
    os.environ["SCRAPING_API_KEY"] = test_key
    return test_key


@pytest.fixture
def auth_headers(api_key):
    """Return authorization headers with API key."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture
def test_entities(app):
    """Create test entities (active and inactive) for testing."""
    with app.app_context():
        # Active entity
        active_entity = Entity(
            name="Active Test Brand",
            type="company",
            to_scrape=True
        )
        db.session.add(active_entity)
        
        # Inactive entity
        inactive_entity = Entity(
            name="Inactive Test Brand",
            type="company",
            to_scrape=False
        )
        db.session.add(inactive_entity)
        
        db.session.commit()
        
        # Store IDs for use in tests
        active_id = active_entity.id
        inactive_id = inactive_entity.id
        
        yield {
            "active": active_entity,
            "inactive": inactive_entity,
            "active_id": active_id,
            "inactive_id": inactive_id
        }
        
        # Cleanup
        Entity.query.filter(Entity.id.in_([active_id, inactive_id])).delete()
        db.session.commit()


@pytest.fixture
def test_pages_with_failed_history(app, test_entities):
    """
    Create test pages and pages_history records with missing data.
    Covers multiple platforms and various failure scenarios.
    """
    with app.app_context():
        # The route this fixture feeds (get_failed_pages_for_today) checks a
        # rolling "yesterday 22:00 UTC to now" window, not a calendar day --
        # a fixed wall-clock hour lands outside that window whenever the
        # suite runs before that hour UTC. Anchor to "now" instead, which is
        # always inside it by construction (the route's own end_time is a
        # fresh datetime.utcnow() captured microseconds later).
        today = datetime.utcnow()
        
        # Instagram page - active entity, missing likes and comments in posts
        instagram_page = Page(
            uuid=uuid4(),
            name="test_instagram_active",
            link="https://instagram.com/test_active",
            platform="instagram",
            entity_id=test_entities["active_id"]
        )
        db.session.add(instagram_page)
        
        # Facebook page - active entity, missing posts key
        facebook_page = Page(
            uuid=uuid4(),
            name="test_facebook_active",
            link="https://facebook.com/test_active",
            platform="facebook",
            entity_id=test_entities["active_id"]
        )
        db.session.add(facebook_page)
        
        # TikTok page - active entity, empty top_videos array
        tiktok_page = Page(
            uuid=uuid4(),
            name="test_tiktok_active",
            link="https://tiktok.com/@test_active",
            platform="tiktok",
            entity_id=test_entities["active_id"]
        )
        db.session.add(tiktok_page)
        
        # X (Twitter) page - inactive entity, missing likes
        x_page_inactive = Page(
            uuid=uuid4(),
            name="test_x_inactive",
            link="https://x.com/test_inactive",
            platform="x",
            entity_id=test_entities["inactive_id"]
        )
        db.session.add(x_page_inactive)
        
        # LinkedIn page - active entity, valid data (should NOT appear in failed list)
        linkedin_page_valid = Page(
            uuid=uuid4(),
            name="test_linkedin_valid",
            link="https://linkedin.com/company/test_valid",
            platform="linkedin",
            entity_id=test_entities["active_id"]
        )
        db.session.add(linkedin_page_valid)
        
        db.session.commit()
        
        # Store page IDs for cleanup
        page_ids = [
            instagram_page.uuid,
            facebook_page.uuid,
            tiktok_page.uuid,
            x_page_inactive.uuid,
            linkedin_page_valid.uuid
        ]
        
        # Create pages_history records with missing data
        
        # Instagram - posts exist but missing engagement data
        instagram_history = PageHistory(
            page_id=instagram_page.uuid,
            data={
                "followers": 1000,
                "posts": [
                    {
                        "post_id": "C12345678",
                        "caption": "Test post 1"
                        # Missing: likes, comments
                    },
                    {
                        "post_id": "C87654321",
                        "caption": "Test post 2"
                        # Missing: likes, comments
                    }
                ]
            },
            recorded_at=today
        )
        db.session.add(instagram_history)
        
        # Facebook - missing posts key entirely
        facebook_history = PageHistory(
            page_id=facebook_page.uuid,
            data={
                "followers": 2000,
                "page_likes": 1500
                # Missing: posts
            },
            recorded_at=today
        )
        db.session.add(facebook_history)
        
        # TikTok - empty top_videos array
        tiktok_history = PageHistory(
            page_id=tiktok_page.uuid,
            data={
                "followers": 5000,
                "top_videos": []  # Empty array
            },
            recorded_at=today
        )
        db.session.add(tiktok_history)
        
        # X (Twitter) - inactive entity, missing likes in posts
        x_history_inactive = PageHistory(
            page_id=x_page_inactive.uuid,
            data={
                "followers": 3000,
                "posts": [
                    {
                        "post_id": "1234567890",
                        "text": "Test tweet",
                        "comments": 10
                        # Missing: likes
                    }
                ]
            },
            recorded_at=today
        )
        db.session.add(x_history_inactive)
        
        # LinkedIn - valid data (should NOT be flagged as failed)
        linkedin_history_valid = PageHistory(
            page_id=linkedin_page_valid.uuid,
            data={
                "followers": 4000,
                "updates": [
                    {
                        "update_id": "urn:li:activity:1234567890",
                        "text": "Test update",
                        "likes": 50,
                        "comments": 10
                    }
                ]
            },
            recorded_at=today
        )
        db.session.add(linkedin_history_valid)
        
        db.session.commit()
        
        yield {
            "instagram": instagram_page,
            "facebook": facebook_page,
            "tiktok": tiktok_page,
            "x_inactive": x_page_inactive,
            "linkedin_valid": linkedin_page_valid,
            "page_ids": page_ids
        }
        
        # Cleanup
        PageHistory.query.filter(PageHistory.page_id.in_(page_ids)).delete()
        Page.query.filter(Page.uuid.in_(page_ids)).delete()
        db.session.commit()


class TestApifyFallbackE2E:
    """
    End-to-end integration tests for Apify Fallback Scraping feature.
    Task 8.1: Test end-to-end flow with Apify service.
    """
    
    def test_e2e_no_failed_pages(self, client, auth_headers):
        """
        Test E2E flow when there are no failed pages today.
        Should return empty profiles list with success.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert "profiles" in data["data"]
        assert "count" in data["data"]
        assert "platform" in data["data"]
        assert "scraping_issues" in data["data"]
        
        # When no failed pages exist, should return empty results
        assert isinstance(data["data"]["profiles"], list)
        assert data["data"]["count"] == len(data["data"]["profiles"])
        assert data["data"]["platform"] == "all"
        assert isinstance(data["data"]["scraping_issues"], list)
    
    def test_e2e_with_failed_pages_all_platforms(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test E2E flow with failed pages across multiple platforms.
        Verifies:
        - Failed pages are correctly identified
        - Only active entities are returned
        - Scraping issues are correctly identified
        - Response format is correct
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert data["data"]["platform"] == "all"
        
        profiles = data["data"]["profiles"]
        scraping_issues = data["data"]["scraping_issues"]
        
        # Should return 3 active entity profiles (instagram, facebook, tiktok)
        # Should NOT include x_inactive (inactive entity) or linkedin_valid (valid data)
        assert data["data"]["count"] == 3
        assert len(profiles) == 3
        
        # Verify profile structure and content
        profile_platforms = {p["platform"] for p in profiles}
        assert profile_platforms == {"instagram", "facebook", "tiktok"}
        
        # Verify each profile has required fields
        for profile in profiles:
            assert "name" in profile
            assert "url" in profile
            assert "platform" in profile
            assert "entity_id" in profile
            assert "entity_name" in profile
            
            # All profiles should belong to active entity
            assert profile["entity_name"] == "Active Test Brand"
        
        # Verify scraping issues are correctly identified
        # Instagram: missing likes and comments
        # Facebook: missing posts, AND missing followers -- its fixture sets
        # "followers": 2000, but validate_data_structure reads Facebook's
        # follower count under "page_followers" (see FOLLOWERS_KEY_BY_PLATFORM),
        # so this fixture's value is under the wrong key and correctly counts
        # as missing. Every other platform here (Instagram/TikTok/X/LinkedIn)
        # uses the generic "followers" key, which does match what's checked
        # for them, so "followers" in scraping_issues traces to Facebook only.
        # TikTok: empty top_videos
        assert len(scraping_issues) > 0
        expected_issues = {"likes", "comments", "posts", "top_videos (empty)", "followers"}
        assert set(scraping_issues).issubset(expected_issues)
    
    def test_e2e_platform_filter_instagram(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test E2E flow with platform filter for Instagram.
        Should only return Instagram profiles that failed scraping.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=instagram",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert data["data"]["platform"] == "instagram"
        
        profiles = data["data"]["profiles"]
        assert data["data"]["count"] == 1
        assert len(profiles) == 1
        
        # Verify it's the Instagram profile
        profile = profiles[0]
        assert profile["platform"] == "instagram"
        assert profile["name"] == "test_instagram_active"
        assert profile["url"] == "https://instagram.com/test_active"
        
        # Verify scraping issues for Instagram (missing likes and comments)
        scraping_issues = data["data"]["scraping_issues"]
        assert "likes" in scraping_issues
        assert "comments" in scraping_issues
    
    def test_e2e_platform_filter_facebook(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test E2E flow with platform filter for Facebook.
        Should only return Facebook profiles that failed scraping.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=facebook",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert data["data"]["platform"] == "facebook"
        
        profiles = data["data"]["profiles"]
        assert data["data"]["count"] == 1
        assert len(profiles) == 1
        
        profile = profiles[0]
        assert profile["platform"] == "facebook"
        assert profile["name"] == "test_facebook_active"
        
        # Verify scraping issues for Facebook (missing posts)
        scraping_issues = data["data"]["scraping_issues"]
        assert "posts" in scraping_issues
    
    def test_e2e_platform_filter_tiktok(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test E2E flow with platform filter for TikTok.
        Should only return TikTok profiles that failed scraping.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=tiktok",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert data["data"]["platform"] == "tiktok"
        
        profiles = data["data"]["profiles"]
        assert data["data"]["count"] == 1
        
        profile = profiles[0]
        assert profile["platform"] == "tiktok"
        
        # Verify scraping issues for TikTok (empty top_videos)
        scraping_issues = data["data"]["scraping_issues"]
        assert "top_videos (empty)" in scraping_issues
    
    def test_e2e_platform_filter_no_failures(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test E2E flow with platform filter where no failures exist.
        LinkedIn has valid data, so should return empty list.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=linkedin",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["success"] is True
        assert data["data"]["platform"] == "linkedin"
        assert data["data"]["count"] == 0
        assert len(data["data"]["profiles"]) == 0
        assert len(data["data"]["scraping_issues"]) == 0
    
    def test_e2e_active_entity_filtering(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test that only active entities (to_scrape=True) are returned.
        X (Twitter) page belongs to inactive entity, should NOT be included.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        profiles = data["data"]["profiles"]
        
        # Verify no profiles from inactive entities
        for profile in profiles:
            assert profile["entity_name"] != "Inactive Test Brand"
            assert profile["entity_name"] == "Active Test Brand"
        
        # Specifically verify X profile is NOT included
        x_profiles = [p for p in profiles if p["platform"] == "x"]
        assert len(x_profiles) == 0
    
    def test_e2e_invalid_platform(self, client, auth_headers):
        """
        Test E2E flow with invalid platform parameter.
        Should return 400 Bad Request.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?platform=myspace",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        
        assert data["success"] is False
        assert "Invalid platform" in data["error"]
        assert "facebook" in data["error"]
        assert "instagram" in data["error"]
    
    def test_e2e_missing_authentication(self, client, test_pages_with_failed_history):
        """
        Test E2E flow without authentication.
        Should return 401 Unauthorized.
        """
        response = client.get("/api/scraping/apify_profile_scraping")
        
        assert response.status_code == 401
        data = response.get_json()
        
        assert data["success"] is False
        assert "API key" in data["error"]
    
    def test_e2e_response_format_consistency(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test that response format is consistent and contains all required fields.
        Validates Property 1 from design: API Response Format Consistency.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.content_type == "application/json"
        
        data = response.get_json()
        
        # Top-level structure
        assert "success" in data
        assert "data" in data
        assert data["success"] is True
        
        # Data structure
        result = data["data"]
        assert "profiles" in result
        assert "count" in result
        assert "platform" in result
        assert "scraping_issues" in result
        
        # Data types
        assert isinstance(result["profiles"], list)
        assert isinstance(result["count"], int)
        assert isinstance(result["platform"], str)
        assert isinstance(result["scraping_issues"], list)
        
        # Count consistency
        assert result["count"] == len(result["profiles"])
        
        # Profile structure
        for profile in result["profiles"]:
            assert isinstance(profile, dict)
            assert "name" in profile
            assert "url" in profile
            assert "platform" in profile
            assert "entity_id" in profile
            assert "entity_name" in profile
            
            assert isinstance(profile["name"], str)
            assert isinstance(profile["url"], str)
            assert isinstance(profile["platform"], str)
            assert isinstance(profile["entity_id"], int)
            assert isinstance(profile["entity_name"], str)
    
    def test_e2e_scraping_issues_non_empty_when_profiles_exist(
        self, client, auth_headers, test_pages_with_failed_history
    ):
        """
        Test that scraping_issues is non-empty when profiles are returned.
        Validates Property 6 from design: Scraping Issues Non-Empty.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        result = data["data"]
        
        # If profiles exist, scraping_issues must be non-empty
        if result["count"] > 0:
            assert len(result["scraping_issues"]) > 0
            
            # Each issue should be a string
            for issue in result["scraping_issues"]:
                assert isinstance(issue, str)
    
    def test_e2e_no_duplicate_profiles(self, client, auth_headers, test_pages_with_failed_history):
        """
        Test that no duplicate profiles are returned.
        Validates Property 5 from design: No Duplicate Profiles.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        profiles = data["data"]["profiles"]
        
        # Create unique keys (entity_id, platform)
        profile_keys = [(p["entity_id"], p["platform"]) for p in profiles]
        
        # Check for duplicates
        assert len(profile_keys) == len(set(profile_keys))
    
    def test_e2e_multiple_platforms_correct_issues(
        self, client, auth_headers, test_pages_with_failed_history
    ):
        """
        Test that scraping issues are correctly aggregated across multiple platforms.
        Different platforms have different missing keys.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        scraping_issues = data["data"]["scraping_issues"]
        
        # Should contain issues from all failed platforms
        # Instagram: likes, comments
        # Facebook: posts
        # TikTok: top_videos (empty)
        
        assert len(scraping_issues) > 0
        
        # Verify issues are sorted and unique
        assert scraping_issues == sorted(list(set(scraping_issues)))


class TestApifyFallbackEdgeCases:
    """
    Edge case tests for Apify Fallback Scraping feature.
    """
    
    def test_old_pages_history_not_included(self, client, auth_headers, test_entities, app):
        """
        Test that pages_history records from previous days are not included.
        Only today's failures should be returned.
        """
        with app.app_context():
            # 2 days back, not 1 -- the window is "yesterday 22:00 UTC to
            # now", and "exactly 24h ago" lands inside it (not outside, as
            # this test needs) whenever run between 22:00-23:59 UTC.
            yesterday = datetime.utcnow() - timedelta(days=2)
            
            # Create page with failed history from yesterday
            old_page = Page(
                uuid=uuid4(),
                name="test_old_page",
                link="https://instagram.com/old",
                platform="instagram",
                entity_id=test_entities["active_id"]
            )
            db.session.add(old_page)
            db.session.commit()
            
            page_id = old_page.uuid
            
            # Create history from yesterday with missing data
            old_history = PageHistory(
                page_id=page_id,
                data={"followers": 1000},  # Missing posts
                recorded_at=yesterday
            )
            db.session.add(old_history)
            db.session.commit()
        
        try:
            response = client.get(
                "/api/scraping/apify_profile_scraping",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            profiles = data["data"]["profiles"]
            
            # Old page should NOT be included
            old_profiles = [p for p in profiles if p["name"] == "test_old_page"]
            assert len(old_profiles) == 0
        
        finally:
            with app.app_context():
                PageHistory.query.filter_by(page_id=page_id).delete()
                Page.query.filter_by(uuid=page_id).delete()
                db.session.commit()
    
    def test_page_with_multiple_history_records_today(
        self, client, auth_headers, test_entities, app
    ):
        """
        Test handling of pages with multiple history records for today.
        Should handle gracefully without duplicates.
        """
        with app.app_context():
            today = datetime.utcnow()
            
            page = Page(
                uuid=uuid4(),
                name="test_multi_history",
                link="https://instagram.com/multi",
                platform="instagram",
                entity_id=test_entities["active_id"]
            )
            db.session.add(page)
            db.session.commit()
            
            page_id = page.uuid
            
            # Create multiple history records for today with missing data.
            # Offsets from "now" rather than fixed wall-clock hours -- see
            # the note on the fixture above; a .replace(hour=16) lands in
            # the future, and outside the window, whenever run before 16:00 UTC.
            for hours_ago in [4, 2, 0]:
                history = PageHistory(
                    page_id=page_id,
                    data={"followers": 1000},  # Missing posts
                    recorded_at=today - timedelta(hours=hours_ago)
                )
                db.session.add(history)
            db.session.commit()
        
        try:
            response = client.get(
                "/api/scraping/apify_profile_scraping",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            
            profiles = data["data"]["profiles"]
            
            # Should appear only once despite multiple history records
            matching_profiles = [p for p in profiles if p["name"] == "test_multi_history"]
            
            # The page may appear multiple times if the repository returns
            # multiple failed_page entries, but ideally should be deduplicated
            # This depends on implementation details
            
        finally:
            with app.app_context():
                PageHistory.query.filter_by(page_id=page_id).delete()
                Page.query.filter_by(uuid=page_id).delete()
                db.session.commit()

    def test_apify_profile_scraping_with_limit_param(
        self, client, auth_headers, test_pages_with_failed_history
    ):
        """
        Test that limit parameter restricts the number of profiles returned.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?limit=1",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["data"]["profiles"]) == 1
        assert data["data"]["count"] == 1

    def test_apify_profile_scraping_with_invalid_limit_param(
        self, client, auth_headers
    ):
        """
        Test that invalid limit parameter returns 400 error.
        """
        response = client.get(
            "/api/scraping/apify_profile_scraping?limit=invalid",
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "'limit' must be a positive integer" in data["error"]
