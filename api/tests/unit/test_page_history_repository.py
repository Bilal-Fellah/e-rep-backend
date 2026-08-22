"""
Unit tests for PageHistoryRepository.validate_data_structure() helper function.
Tests platform-specific JSONB validation for missing keys.
"""
import pytest
from datetime import date, datetime, time
from uuid import uuid4
from api.repositories.page_history_repository import PageHistoryRepository
from api.models import PageHistory, Page
from api import db


class TestValidateDataStructure:
    """Test suite for validate_data_structure helper function."""

    # Test Instagram platform
    def test_instagram_valid_data_structure(self):
        """Valid Instagram data with posts, likes, comments, and followers should return empty list."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 100,
                    "comments": 50
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []

    def test_instagram_missing_posts_key(self):
        """Instagram data without posts key should return ['posts']."""
        data = {
            "followers": 1000,
            "biography": "Test bio"
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts"]

    def test_instagram_empty_posts_array(self):
        """Instagram data with empty posts array should return ['posts (empty)'] plus
        'followers' since this fixture has no follower count either."""
        data = {
            "posts": []
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts (empty)", "followers"]

    def test_instagram_missing_likes_field(self):
        """Instagram post without likes field should return ['likes'] plus
        'followers' since this fixture has no follower count either."""
        data = {
            "posts": [
                {
                    "post_id": "123",
                    "comments": 50
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["likes", "followers"]

    def test_instagram_missing_comments_field(self):
        """Instagram post without comments field should return ['comments'] plus
        'followers' since this fixture has no follower count either."""
        data = {
            "posts": [
                {
                    "post_id": "123",
                    "likes": 100
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["comments", "followers"]

    def test_instagram_missing_both_engagement_fields(self):
        """Instagram post without likes and comments should return both, plus
        'followers' since this fixture has no follower count either."""
        data = {
            "posts": [
                {
                    "post_id": "123",
                    "caption": "Test post"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert set(result) == {"likes", "comments", "followers"}

    # Test TikTok platform (uses top_videos)
    def test_tiktok_valid_data_structure(self):
        """Valid TikTok data with top_videos and followers should return empty list."""
        data = {
            "followers": 50000,
            "top_videos": [
                {
                    "video_id": "123",
                    "diggCount": 1000,
                    "commentCount": 200
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "tiktok")
        assert result == []

    def test_tiktok_missing_top_videos_key(self):
        """TikTok data without top_videos key should return ['top_videos']."""
        data = {
            "followers": 50000,
            "biography": "TikTok bio"
        }
        result = PageHistoryRepository.validate_data_structure(data, "tiktok")
        assert result == ["top_videos"]

    def test_tiktok_supports_digg_count_variation(self):
        """TikTok should recognize diggCount as a valid likes field."""
        data = {
            "followers": 50000,
            "top_videos": [
                {
                    "video_id": "123",
                    "diggCount": 1000,
                    "commentCount": 200
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "tiktok")
        assert result == []

    # Test LinkedIn platform (uses updates)
    def test_linkedin_valid_data_structure(self):
        """Valid LinkedIn data with updates and followers should return empty list."""
        data = {
            "followers": 2000,
            "updates": [
                {
                    "update_id": "123",
                    "likes": 50,
                    "comments": 10
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "linkedin")
        assert result == []

    def test_linkedin_missing_updates_key(self):
        """LinkedIn data without updates key should return ['updates']."""
        data = {
            "followers": 2000,
            "about": "Company description"
        }
        result = PageHistoryRepository.validate_data_structure(data, "linkedin")
        assert result == ["updates"]

    # Test YouTube platform (uses top_videos)
    def test_youtube_valid_data_structure(self):
        """Valid YouTube data with top_videos and subscribers should return empty list."""
        data = {
            "subscribers": 100000,
            "top_videos": [
                {
                    "video_id": "abc123",
                    "likes": 5000,
                    "comments": 300
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "youtube")
        assert result == []

    def test_youtube_missing_top_videos_key(self):
        """YouTube data without top_videos key should return ['top_videos']."""
        data = {
            "subscribers": 100000,
            "Description": "Channel description"
        }
        result = PageHistoryRepository.validate_data_structure(data, "youtube")
        assert result == ["top_videos"]

    # Test X (Twitter) platform
    def test_x_valid_data_structure(self):
        """Valid X (Twitter) data with posts and followers should return empty list."""
        data = {
            "followers": 500,
            "posts": [
                {
                    "tweet_id": "123",
                    "likes": 500,
                    "comments": 50
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "x")
        assert result == []

    # Test Facebook platform
    def test_facebook_valid_data_structure(self):
        """Valid Facebook data with posts and page_followers should return empty list."""
        data = {
            "page_followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 200,
                    "comments": 30
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "facebook")
        assert result == []

    # Test engagement field variations
    def test_likes_count_variation(self):
        """Should recognize likesCount as a valid likes field."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likesCount": 100,
                    "commentsCount": 20
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []

    def test_like_count_variation(self):
        """Should recognize likeCount as a valid likes field."""
        data = {
            "page_followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likeCount": 100,
                    "commentCount": 20
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "facebook")
        assert result == []

    # Test edge cases
    def test_null_data_input(self):
        """Null data should return missing posts key, plus 'followers' since
        there is no data at all to have a follower count either."""
        result = PageHistoryRepository.validate_data_structure(None, "instagram")
        assert result == ["posts", "followers"]

    def test_posts_is_not_array(self):
        """Posts key with non-array value should return ['posts'] plus
        'followers' since this fixture has no follower count either."""
        data = {
            "posts": "not an array"
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts", "followers"]

    def test_posts_is_dict_not_list(self):
        """Posts key with dict value should return ['posts'] plus 'followers'
        since this fixture has no follower count either."""
        data = {
            "posts": {"post_id": "123"}
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts", "followers"]

    def test_engagement_fields_with_null_values(self):
        """Engagement fields with null values should be treated as missing,
        plus 'followers' since this fixture has no follower count either."""
        data = {
            "posts": [
                {
                    "post_id": "123",
                    "likes": None,
                    "comments": None
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert set(result) == {"likes", "comments", "followers"}

    def test_engagement_fields_with_zero_values(self):
        """Engagement fields with zero values are valid (0 is not None)."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 0,
                    "comments": 0
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []

    def test_multiple_posts_only_checks_first(self):
        """Validation should only check the first post in the array."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 100,
                    "comments": 50
                },
                {
                    "post_id": "456"
                    # Missing likes and comments in second post
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []  # First post is valid, so result is empty

    def test_unknown_platform_defaults_to_posts(self):
        """Unknown platform should default to 'posts' key, and to the
        generic 'followers' key for the follower check too."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 100,
                    "comments": 50
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "unknown_platform")
        assert result == []

    def test_case_sensitive_platform_names(self):
        """Platform names should be case-sensitive (lowercase expected)."""
        data = {
            "followers": 1000,
            "posts": [
                {
                    "post_id": "123",
                    "likes": 100,
                    "comments": 50
                }
            ]
        }
        # Should work with lowercase
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []



class TestGetFailedPagesForToday:
    """Test suite for get_failed_pages_for_today() method."""

    def test_returns_empty_list_when_no_history_records_today(self, app):
        """Should return empty list when no pages_history records exist for today."""
        with app.app_context():
            result = PageHistoryRepository.get_failed_pages_for_today()
            assert isinstance(result, list)
            assert len(result) == 0

    def test_returns_empty_list_when_all_records_valid(self, app, sample_page):
        """Should return empty list when all today's records pass validation."""
        with app.app_context():
            # Create a valid page history record for today
            valid_data = {
                "followers": 1000,
                "posts": [
                    {
                        "post_id": "123",
                        "likes": 100,
                        "comments": 50
                    }
                ]
            }
            history = PageHistory(
                page_id=sample_page.uuid,
                data=valid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 0

    def test_detects_missing_posts_key(self, app, sample_page):
        """Should detect pages with missing posts key in data."""
        with app.app_context():
            # Create page history with missing posts key
            invalid_data = {
                "followers": 1000,
                "biography": "Test bio"
            }
            history = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert result[0]["page_id"] == sample_page.uuid
            assert result[0]["platform"] == sample_page.platform
            assert "posts" in result[0]["missing_keys"]
            assert isinstance(result[0]["recorded_at"], datetime)

    def test_detects_missing_likes_field(self, app, sample_page):
        """Should detect pages with posts missing likes field."""
        with app.app_context():
            invalid_data = {
                "posts": [
                    {
                        "post_id": "123",
                        "comments": 50
                    }
                ]
            }
            history = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert "likes" in result[0]["missing_keys"]

    def test_detects_missing_comments_field(self, app, sample_page):
        """Should detect pages with posts missing comments field."""
        with app.app_context():
            invalid_data = {
                "posts": [
                    {
                        "post_id": "123",
                        "likes": 100
                    }
                ]
            }
            history = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert "comments" in result[0]["missing_keys"]

    def test_detects_empty_posts_array(self, app, sample_page):
        """Should detect pages with empty posts array."""
        with app.app_context():
            invalid_data = {
                "posts": []
            }
            history = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert "posts (empty)" in result[0]["missing_keys"]

    def test_handles_multiple_failed_pages(self, app, sample_page, sample_page_tiktok):
        """Should detect multiple failed pages in same day."""
        with app.app_context():
            # Create two invalid page history records
            invalid_data_1 = {
                "posts": [{"post_id": "123"}]  # Missing likes and comments
            }
            invalid_data_2 = {
                "top_videos": []  # Empty array for TikTok
            }
            
            history_1 = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data_1,
                recorded_at=datetime.combine(date.today(), time(10, 0))
            )
            history_2 = PageHistory(
                page_id=sample_page_tiktok.uuid,
                data=invalid_data_2,
                recorded_at=datetime.combine(date.today(), time(14, 0))
            )
            db.session.add_all([history_1, history_2])
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 2
            page_ids = [r["page_id"] for r in result]
            assert sample_page.uuid in page_ids
            assert sample_page_tiktok.uuid in page_ids

    def test_handles_platform_specific_keys_tiktok(self, app, sample_page_tiktok):
        """Should use top_videos key for TikTok platform."""
        with app.app_context():
            # Missing top_videos key (TikTok-specific)
            invalid_data = {
                "followers": 50000,
                "biography": "TikTok bio"
            }
            history = PageHistory(
                page_id=sample_page_tiktok.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert "top_videos" in result[0]["missing_keys"]

    def test_handles_platform_specific_keys_linkedin(self, app, sample_page_linkedin):
        """Should use updates key for LinkedIn platform."""
        with app.app_context():
            # Missing updates key (LinkedIn-specific)
            invalid_data = {
                "followers": 2000,
                "about": "Company description"
            }
            history = PageHistory(
                page_id=sample_page_linkedin.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            assert "updates" in result[0]["missing_keys"]

    def test_only_includes_todays_records(self, app, sample_page):
        """Should only return today's failed records, not yesterday's."""
        with app.app_context():
            from datetime import timedelta
            
            # Create invalid record for yesterday
            yesterday = date.today() - timedelta(days=1)
            invalid_data = {"posts": []}
            
            history_yesterday = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(yesterday, time(12, 0))
            )
            db.session.add(history_yesterday)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 0  # Should not include yesterday's record

    def test_returns_correct_structure(self, app, sample_page):
        """Should return list of dicts with correct keys."""
        with app.app_context():
            invalid_data = {"posts": []}
            history = PageHistory(
                page_id=sample_page.uuid,
                data=invalid_data,
                recorded_at=datetime.combine(date.today(), time(12, 0))
            )
            db.session.add(history)
            db.session.commit()

            result = PageHistoryRepository.get_failed_pages_for_today()
            assert len(result) == 1
            
            failed_page = result[0]
            assert "page_id" in failed_page
            assert "platform" in failed_page
            assert "missing_keys" in failed_page
            assert "recorded_at" in failed_page
            
            # Verify types
            assert isinstance(failed_page["missing_keys"], list)
            assert isinstance(failed_page["recorded_at"], datetime)
            assert isinstance(failed_page["platform"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
