"""
Tests to verify correct behavior of get_entity_top_posts.
These tests ensure that first-time posts are included with their current metrics as gains.
"""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from api.services.entity_service import EntityService


class TestTopPostsFirstTimePosts:
    """
    Tests for first-time posts appearing on the target date.
    These posts should be included with their current metric values as gains (baseline = 0).
    """

    def test_first_time_post_on_target_date_is_included(self, monkeypatch):
        """
        A post that appears for the first time on the target date should be included.
        Its current metrics are treated as gains (as if baseline was 0).
        """
        rows = [
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "new_post", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 50}]],
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, posts_num, skipped = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert posts_num == 1, "Post should have been processed"
        assert day_gains is not None, "Should return data for the target date"
        assert day_gains["day"] == "2026-01-20"
        
        # First-time post is now included with gains = current values
        assert len(day_gains["posts"]) == 1, "First-time post should be included"
        assert day_gains["posts"][0]["gained_comments"] == 10
        assert day_gains["posts"][0]["gained_likes"] == 50
        assert day_gains["posts"][0]["post_id"] == "new_post"

    def test_post_with_previous_day_computes_gains(self, monkeypatch):
        """
        Posts with a previous snapshot should compute gains as the difference.
        """
        rows = [
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "existing_post", "datetime": "2026-01-19T00:00:00Z", "comments": 5, "likes": 20}]],
            ),
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "existing_post", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 50}]],
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, posts_num, skipped = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert day_gains is not None
        assert len(day_gains["posts"]) == 1
        assert day_gains["posts"][0]["gained_comments"] == 5
        assert day_gains["posts"][0]["gained_likes"] == 30

    def test_mixed_posts_first_time_and_existing(self, monkeypatch):
        """
        Test with mixed scenario: some posts are new, some have previous data.
        Both should be included with correct gains.
        """
        rows = [
            # Day 1 - only post_a exists
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_a", "datetime": "2026-01-19T00:00:00Z", "comments": 5, "likes": 10}]],
            ),
            # Day 2 - post_a has more metrics, post_b is NEW
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[
                    {"id": "post_a", "datetime": "2026-01-20T00:00:00Z", "comments": 10, "likes": 20},
                    {"id": "post_b", "datetime": "2026-01-20T00:00:00Z", "comments": 100, "likes": 200},  # NEW post!
                ]],
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, posts_num, skipped = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert day_gains is not None
        # posts_num counts all posts processed across all days (1 from day 1 + 2 from day 2 = 3)
        assert posts_num == 3, "All posts should be processed"
        
        # Both posts should be included
        assert len(day_gains["posts"]) == 2, "Both posts should be in results"
        
        # post_a has gains from previous day
        post_a = next((p for p in day_gains["posts"] if p["post_id"] == "post_a"), None)
        assert post_a is not None
        assert post_a["gained_comments"] == 5
        assert post_a["gained_likes"] == 10
        
        # post_b is new, gains = current values
        post_b = next((p for p in day_gains["posts"] if p["post_id"] == "post_b"), None)
        assert post_b is not None
        assert post_b["gained_comments"] == 100
        assert post_b["gained_likes"] == 200


class TestTopPostsFirstDayOfData:
    """
    Tests for the edge case when the target date is the first day of data.
    """

    def test_target_date_is_first_day_of_data_returns_posts(self, monkeypatch):
        """
        When requesting data for the first day available, posts should be returned
        with their current metrics as gains.
        """
        rows = [
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_1", "datetime": "2026-01-20T00:00:00Z", "comments": 50, "likes": 100}]],
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, posts_num, skipped = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert day_gains is not None, "Should return data for target date"
        assert day_gains["day"] == "2026-01-20"
        
        # Posts are now included on first day
        assert len(day_gains["posts"]) == 1
        assert day_gains["posts"][0]["gained_comments"] == 50
        assert day_gains["posts"][0]["gained_likes"] == 100


class TestTopPostsGainsComputation:
    """
    Tests to verify gains are computed correctly for posts.
    """

    def test_negative_gains_are_included(self, monkeypatch):
        """
        Posts with decreased metrics (negative gains) should still be included.
        """
        rows = [
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_1", "datetime": "2026-01-19T00:00:00Z", "comments": 50, "likes": 100}]],
            ),
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_1", "datetime": "2026-01-20T00:00:00Z", "comments": 30, "likes": 80}]],  # Decreased!
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, _, _ = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert day_gains is not None
        assert len(day_gains["posts"]) == 1
        assert day_gains["posts"][0]["gained_comments"] == -20
        assert day_gains["posts"][0]["gained_likes"] == -20

    def test_zero_gains_are_included(self, monkeypatch):
        """
        Posts with no change in metrics should still be included.
        """
        rows = [
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_1", "datetime": "2026-01-19T00:00:00Z", "comments": 50, "likes": 100}]],
            ),
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "post_1", "datetime": "2026-01-20T00:00:00Z", "comments": 50, "likes": 100}]],  # No change
            ),
        ]
        monkeypatch.setattr(
            "api.services.entity_service.EntityRepository.get_entity_posts_metrics",
            lambda entity_id, date_limit: rows,
        )

        day_gains, _, _ = EntityService.get_entity_top_posts(1, date_value="2026-01-20", top_posts=5)

        assert day_gains is not None
        assert len(day_gains["posts"]) == 1
        assert day_gains["posts"][0]["gained_comments"] == 0
        assert day_gains["posts"][0]["gained_likes"] == 0
