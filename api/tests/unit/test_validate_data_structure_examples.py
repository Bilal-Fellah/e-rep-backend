"""
Example-based tests for validate_data_structure showing realistic data scenarios.
These tests demonstrate how the function would work with actual scraped data.
"""
import pytest
from api.repositories.page_history_repository import PageHistoryRepository


class TestValidateDataStructureExamples:
    """Example-based tests with realistic scraped data structures."""

    def test_realistic_instagram_profile_complete(self):
        """Complete Instagram profile data should pass validation."""
        data = {
            "followers": 25000,
            "following": 500,
            "biography": "Official Instagram account",
            "profile_image_link": "https://example.com/profile.jpg",
            "posts": [
                {
                    "post_id": "C12345ABC",
                    "shortcode": "ABC123",
                    "caption": "Check out our new product!",
                    "likes": 1500,
                    "comments": 250,
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                {
                    "post_id": "C67890DEF",
                    "shortcode": "DEF456",
                    "caption": "Behind the scenes",
                    "likes": 2100,
                    "comments": 180,
                    "timestamp": "2024-01-14T15:20:00Z"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == []

    def test_realistic_tiktok_profile_complete(self):
        """Complete TikTok profile data should pass validation."""
        data = {
            "followers": 150000,
            "following": 200,
            "biography": "TikTok creator",
            "profile_pic_url": "https://example.com/avatar.jpg",
            "top_videos": [
                {
                    "video_id": "7123456789012345678",
                    "description": "Viral video #fyp",
                    "diggCount": 50000,
                    "commentCount": 1200,
                    "shareCount": 5000,
                    "playCount": 500000,
                    "createTime": 1705320000
                },
                {
                    "video_id": "7123456789012345679",
                    "description": "Tutorial video",
                    "diggCount": 25000,
                    "commentCount": 800,
                    "shareCount": 2500,
                    "playCount": 250000,
                    "createTime": 1705233600
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "tiktok")
        assert result == []

    def test_realistic_linkedin_profile_complete(self):
        """Complete LinkedIn profile data should pass validation."""
        data = {
            "followers": 50000,
            "about": "Leading technology company",
            "logo": "https://example.com/logo.png",
            "updates": [
                {
                    "update_id": "urn:li:activity:123456789",
                    "text": "We're hiring! Join our team.",
                    "likes": 500,
                    "comments": 45,
                    "shares": 120,
                    "posted_date": "2024-01-15"
                },
                {
                    "update_id": "urn:li:activity:987654321",
                    "text": "New product launch announcement",
                    "likes": 800,
                    "comments": 92,
                    "shares": 250,
                    "posted_date": "2024-01-12"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "linkedin")
        assert result == []

    def test_realistic_youtube_profile_complete(self):
        """Complete YouTube profile data should pass validation."""
        data = {
            "subscribers": 500000,
            "Description": "Educational content creator",
            "profile_image": "https://example.com/channel.jpg",
            "top_videos": [
                {
                    "video_id": "dQw4w9WgXcQ",
                    "title": "How to code in Python",
                    "likes": 15000,
                    "comments": 2500,
                    "views": 750000,
                    "publishedAt": "2024-01-10T12:00:00Z"
                },
                {
                    "video_id": "abc123def456",
                    "title": "Advanced JavaScript tips",
                    "likes": 12000,
                    "comments": 1800,
                    "views": 600000,
                    "publishedAt": "2024-01-05T14:30:00Z"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "youtube")
        assert result == []

    def test_realistic_instagram_incomplete_scrape(self):
        """Instagram profile with incomplete scraping (no engagement data)."""
        data = {
            "followers": 25000,
            "following": 500,
            "biography": "Official Instagram account",
            "profile_image_link": "https://example.com/profile.jpg",
            "posts": [
                {
                    "post_id": "C12345ABC",
                    "shortcode": "ABC123",
                    "caption": "Check out our new product!",
                    "timestamp": "2024-01-15T10:30:00Z"
                    # Missing likes and comments
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert set(result) == {"likes", "comments"}

    def test_realistic_tiktok_failed_scrape_no_videos(self):
        """TikTok profile where video scraping failed completely."""
        data = {
            "followers": 150000,
            "following": 200,
            "biography": "TikTok creator",
            "profile_pic_url": "https://example.com/avatar.jpg"
            # Missing top_videos array
        }
        result = PageHistoryRepository.validate_data_structure(data, "tiktok")
        assert result == ["top_videos"]

    def test_realistic_linkedin_empty_updates(self):
        """LinkedIn profile with no recent updates."""
        data = {
            "followers": 50000,
            "about": "Leading technology company",
            "logo": "https://example.com/logo.png",
            "updates": []  # Empty array
        }
        result = PageHistoryRepository.validate_data_structure(data, "linkedin")
        assert result == ["updates (empty)"]

    def test_realistic_facebook_with_alternate_field_names(self):
        """Facebook profile using different engagement field names."""
        data = {
            "page_followers": 100000,
            "page_about": "Official Facebook page",
            "posts": [
                {
                    "post_id": "123456789_987654321",
                    "message": "New product announcement",
                    "likesCount": 5000,  # Using likesCount instead of likes
                    "commentsCount": 350,  # Using commentsCount instead of comments
                    "created_time": "2024-01-15T10:00:00+0000"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "facebook")
        assert result == []

    def test_realistic_x_twitter_profile(self):
        """X (Twitter) profile with complete data."""
        data = {
            "followers": 75000,
            "biography": "Tech news and updates",
            "profile_image_link": "https://example.com/profile.jpg",
            "posts": [
                {
                    "tweet_id": "1234567890123456789",
                    "text": "Breaking news in tech industry",
                    "likes": 3000,
                    "comments": 450,
                    "retweets": 1200,
                    "created_at": "2024-01-15T08:30:00Z"
                }
            ]
        }
        result = PageHistoryRepository.validate_data_structure(data, "x")
        assert result == []

    def test_realistic_scraper_timeout_partial_data(self):
        """Profile where scraper timed out and only got follower data."""
        data = {
            "followers": 50000,
            "biography": "Account bio",
            "profile_image_link": "https://example.com/profile.jpg"
            # Scraper timed out before getting posts
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts"]

    def test_realistic_api_rate_limit_empty_posts(self):
        """Profile where API rate limit resulted in empty posts array."""
        data = {
            "followers": 30000,
            "biography": "Account bio",
            "profile_image_link": "https://example.com/profile.jpg",
            "posts": []  # API rate limited, couldn't get posts
        }
        result = PageHistoryRepository.validate_data_structure(data, "instagram")
        assert result == ["posts (empty)"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
