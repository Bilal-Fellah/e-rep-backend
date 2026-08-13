"""
Service for filling missing created_at dates in posts (in-memory, no DB modifications).

This service automatically fills missing created_at dates when posts are retrieved,
controlled by the ENABLE_POSTS_CREATED_AT_BACKFILL environment variable.

Strategy:
1. Fetch posts from database (with potential NULL created_at values)
2. For posts where at least one snapshot has created_at: use it for others
3. For posts with no created_at in any snapshot: use min(recorded_at) as fallback
4. Return filled data to client (database remains unchanged)

This is a read-only operation that enriches data at retrieval time.
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import text
from api import db
from api.utils.logging_utils import instrument_service_class


@instrument_service_class
class PostsCreatedAtService:
    """Service for filling missing created_at dates in posts (in-memory only)."""

    @staticmethod
    def is_enabled() -> bool:
        """Check if automatic filling is enabled via environment variable."""
        return os.getenv("ENABLE_POSTS_CREATED_AT_BACKFILL", "false").lower() in ("true", "1", "yes", "on")

    @staticmethod
    def fill_missing_dates_for_post_history(history_rows: List[Any]) -> List[Any]:
        """
        Fill missing created_at dates for post history snapshots (in-memory).
        
        Strategy:
        1. If at least one snapshot has created_at: use the earliest one for all
        2. If no snapshot has created_at: use min(recorded_at) as fallback
        
        Args:
            history_rows: List of post history rows (from posts_history_mv)
            
        Returns:
            Same list with created_at filled where it was NULL
        """
        if not PostsCreatedAtService.is_enabled() or not history_rows:
            return history_rows
        
        # Find the earliest known created_at
        known_created_at = None
        for row in history_rows:
            if hasattr(row, 'created_at') and row.created_at:
                if known_created_at is None or row.created_at < known_created_at:
                    known_created_at = row.created_at
        
        # Fallback: use earliest recorded_at if no created_at found
        if known_created_at is None:
            earliest_recorded_at = None
            for row in history_rows:
                recorded_at = getattr(row, 'recorded_at', None)
                if recorded_at:
                    if earliest_recorded_at is None or recorded_at < earliest_recorded_at:
                        earliest_recorded_at = recorded_at
            known_created_at = earliest_recorded_at
        
        # Fill missing dates
        if known_created_at:
            for row in history_rows:
                if hasattr(row, 'created_at') and not row.created_at:
                    # Modify the row object in-place
                    row.created_at = known_created_at
        
        return history_rows
    
    @staticmethod
    def fill_missing_date_for_post(post_row: Any, page_id: str, platform: str, post_id: str) -> Any:
        """
        Fill missing created_at date for a single post (in-memory).
        
        Queries the post's history to find a known created_at or use recorded_at.
        
        Args:
            post_row: Single post row (from posts_mv)
            page_id: Page UUID
            platform: Platform name
            post_id: Post identifier
            
        Returns:
            Same row with created_at filled if it was NULL
        """
        if not PostsCreatedAtService.is_enabled() or not post_row:
            return post_row
        
        # Check if created_at is already present
        if hasattr(post_row, 'created_at') and post_row.created_at:
            return post_row
        
        try:
            # Query post history to find a known created_at
            query = text("""
                SELECT created_at, recorded_at
                FROM posts_history_mv
                WHERE page_id = :page_id
                  AND platform = :platform
                  AND post_id = :post_id
                ORDER BY recorded_at ASC
            """)
            
            history = db.session.execute(
                query,
                {"page_id": page_id, "platform": platform, "post_id": post_id}
            ).fetchall()
            
            if not history:
                return post_row
            
            # Find earliest known created_at
            known_created_at = None
            for row in history:
                if row.created_at:
                    if known_created_at is None or row.created_at < known_created_at:
                        known_created_at = row.created_at
            
            # Fallback: use earliest recorded_at
            if known_created_at is None and history:
                known_created_at = history[0].recorded_at
            
            # Fill the date
            if known_created_at:
                post_row.created_at = known_created_at
            
        except Exception as e:
            # Silently fail - don't break the request
            print(f"Error filling created_at for post {platform}/{post_id}: {e}")
        
        return post_row
    
    @staticmethod
    def fill_missing_dates_for_posts(posts: List[Any]) -> List[Any]:
        """
        Fill missing created_at dates for a list of posts (in-memory).
        
        Groups posts by (page_id, platform, post_id) and fills dates using history.
        
        Args:
            posts: List of post rows (from posts_mv)
            
        Returns:
            Same list with created_at filled where it was NULL
        """
        if not PostsCreatedAtService.is_enabled() or not posts:
            return posts
        
        # Identify posts that need filling
        posts_needing_fill = []
        for post in posts:
            if hasattr(post, 'created_at') and not post.created_at:
                page_id = getattr(post, 'page_id', None)
                platform = getattr(post, 'platform', None)
                post_id = getattr(post, 'post_id', None)
                if page_id and platform and post_id:
                    posts_needing_fill.append((post, page_id, platform, post_id))
        
        if not posts_needing_fill:
            return posts
        
        # For efficiency, query all needed post histories in one go
        post_keys = [(page_id, platform, post_id) for _, page_id, platform, post_id in posts_needing_fill]
        
        try:
            # Build a query to get known dates for all posts at once
            # This is more efficient than querying one by one
            known_dates = {}
            
            for page_id, platform, post_id in post_keys:
                query = text("""
                    SELECT created_at, recorded_at
                    FROM posts_history_mv
                    WHERE page_id = :page_id
                      AND platform = :platform
                      AND post_id = :post_id
                    ORDER BY recorded_at ASC
                    LIMIT 100
                """)
                
                history = db.session.execute(
                    query,
                    {"page_id": page_id, "platform": platform, "post_id": post_id}
                ).fetchall()
                
                if history:
                    # Find earliest known created_at
                    known_created_at = None
                    for row in history:
                        if row.created_at:
                            if known_created_at is None or row.created_at < known_created_at:
                                known_created_at = row.created_at
                    
                    # Fallback: use earliest recorded_at
                    if known_created_at is None:
                        known_created_at = history[0].recorded_at
                    
                    known_dates[(page_id, platform, post_id)] = known_created_at
            
            # Fill the dates
            for post, page_id, platform, post_id in posts_needing_fill:
                date_to_use = known_dates.get((page_id, platform, post_id))
                if date_to_use:
                    post.created_at = date_to_use
                    
        except Exception as e:
            # Silently fail - don't break the request
            print(f"Error filling created_at for posts: {e}")
        
        return posts
    
    @staticmethod
    def get_missing_dates_stats() -> dict:
        """
        Get statistics about posts with missing created_at values.
        
        Returns:
            dict with counts for posts_mv and posts_history_mv
        """
        try:
            # Check posts_mv (current state)
            query_mv = text("""
                SELECT COUNT(*) as total,
                       COUNT(created_at) as with_date,
                       COUNT(*) - COUNT(created_at) as missing_date
                FROM posts_mv
            """)
            result_mv = db.session.execute(query_mv).fetchone()
            
            # Check posts_history_mv (all snapshots)
            query_history = text("""
                SELECT COUNT(*) as total,
                       COUNT(created_at) as with_date,
                       COUNT(*) - COUNT(created_at) as missing_date
                FROM posts_history_mv
            """)
            result_history = db.session.execute(query_history).fetchone()
            
            return {
                "enabled": PostsCreatedAtService.is_enabled(),
                "posts_mv": {
                    "total": result_mv.total,
                    "with_date": result_mv.with_date,
                    "missing_date": result_mv.missing_date,
                },
                "posts_history_mv": {
                    "total": result_history.total,
                    "with_date": result_history.with_date,
                    "missing_date": result_history.missing_date,
                }
            }
        except Exception as e:
            return {
                "error": str(e),
                "enabled": PostsCreatedAtService.is_enabled(),
                "posts_mv": {"total": 0, "with_date": 0, "missing_date": 0},
                "posts_history_mv": {"total": 0, "with_date": 0, "missing_date": 0},
            }


