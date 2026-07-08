"""
Tests to expose the bug in get_entity_top_posts.
These tests demonstrate why posts might not be returned when they should be.
"""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from api.services.entity_service import EntityService


class TestTopPostsBugFirstTimePosts:
    """
    BUG: Posts appearing for the first time on the requested date are NOT included.
    
    The get_entity_top_posts method only adds posts to the output if they have
    a previous snapshot to compare against. This means new posts (first appearance)
    are silently dropped.
    """

    def test_first_time_post_on_target_date_is_not_included(self, monkeypatch):
        """
        This test demonstrates the BUG:
        A post that appears for the first time on the target date should be included,
        but it's not because there's no previous snapshot to compare against.
        """
        # A post appears for the first time on 2026-01-20
        # There's no previous data for this post
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

        # EXPECTED: The post should be included (it exists on the target date)
        # ACTUAL: day_gains["posts"] is empty because there's no previous snapshot
        # This demonstrates the bug!
        assert posts_num == 1, "Post should have been processed"
        assert day_gains is not None, "Should return data for the target date"
        
        # THIS ASSERTION WILL FAIL - demonstrating the bug
        # Posts on the first day have no "gains" because there's no previous day,
        # so they're not added to day_output["posts"]
        assert len(day_gains.get("posts", [])) > 0, (
            "BUG: First-time posts should be included in results! "
            "Currently they're dropped because there's no previous snapshot to compare against."
        )

    def test_post_with_previous_day_is_included(self, monkeypatch):
        """
        This test shows that posts WITH a previous snapshot ARE included correctly.
        """
        rows = [
            # Day 1 - post appears with some metrics
            SimpleNamespace(
                platform="instagram",
                recorded_at=datetime(2026, 1, 19, tzinfo=timezone.utc),
                posts_metrics=[[{"id": "existing_post", "datetime": "2026-01-19T00:00:00Z", "comments": 5, "likes": 20}]],
            ),
            # Day 2 - same post with increased metrics
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
        Shows that only posts with previous data are returned.
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
        assert posts_num == 2, "Both posts should be processed"
        
        # BUG: Only post_a is returned, post_b (new post) is dropped
        # Expected: 2 posts, Actual: 1 post
        assert len(day_gains["posts"]) == 1, "BUG CONFIRMED: New post (post_b) was dropped!"
        
        # Only post_a is included because it has previous data
        assert day_gains["posts"][0]["post_id"] == "post_a"


class TestTopPostsNoPreviousDay:
    """
    Tests for the edge case when the target date is the first day of data.
    """

    def test_target_date_is_first_day_of_data_returns_empty(self, monkeypatch):
        """
        When requesting data for the first day available, no posts are returned
        because there's no previous day to compare against.
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

        # day_gains exists but posts is empty
        assert day_gains is not None, "Should return data for target date"
        assert day_gains["day"] == "2026-01-20"
        
        # BUG: posts is empty even though data exists
        assert len(day_gains.get("posts", [])) == 0, (
            "BUG CONFIRMED: No posts returned for first day of data"
        )


class TestTopPostsGainsComputation:
    """
    Tests to verify gains are computed correctly for posts that ARE included.
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
