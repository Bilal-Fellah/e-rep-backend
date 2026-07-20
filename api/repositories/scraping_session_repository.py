# Data-access methods for scraping session repository.
from datetime import datetime, date
from sqlalchemy import func, cast, Date
from api.models.scraping_session_model import ScrapingSession, db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ScrapingSessionRepository:
    """Repository for scraping session database operations."""
    
    @staticmethod
    def create(posts_fetched: int, commit: bool = True) -> ScrapingSession:
        """
        Create a new scraping session with initial post count.
        
        Args:
            posts_fetched: Number of posts fetched
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The created session instance
        """
        session = ScrapingSession(posts_fetched=posts_fetched)
        db.session.add(session)
        if commit:
            db.session.commit()
        return session
    
    @staticmethod
    def get_by_id(session_id: str) -> ScrapingSession | None:
        """
        Fetch a session by ID.
        
        Args:
            session_id: Session UUID
            
        Returns:
            ScrapingSession | None: The session if found
        """
        return ScrapingSession.query.filter_by(session_id=session_id).first()
    
    @staticmethod
    def update_status(session_id: str, status: str, 
                     error_message: str = None, commit: bool = True) -> ScrapingSession:
        """
        Update session status and optional error message.
        
        Args:
            session_id: Session UUID
            status: New status (pending, completed, failed)
            error_message: Optional error message
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.status = status
            if error_message:
                session.error_message = error_message
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def increment_comments(session_id: str, count: int, commit: bool = True) -> ScrapingSession:
        """
        Increment the comments_inserted counter.
        
        Args:
            session_id: Session UUID
            count: Number to increment by
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.comments_inserted += count
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def complete_session(session_id: str, commit: bool = True) -> ScrapingSession:
        """
        Mark session as completed with timestamp.
        
        Args:
            session_id: Session UUID
            commit: Whether to commit the transaction
            
        Returns:
            ScrapingSession: The updated session
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        if session:
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            if commit:
                db.session.commit()
        return session
    
    @staticmethod
    def get_all(limit: int = 100, offset: int = 0) -> list[ScrapingSession]:
        """
        Get all sessions with pagination.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            
        Returns:
            list[ScrapingSession]: List of sessions
        """
        return (ScrapingSession.query
                .order_by(ScrapingSession.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all())
    
    @staticmethod
    def get_recent_failed(since: datetime, limit: int = 20) -> list[ScrapingSession]:
        """Failed sessions created at/after `since`, newest first (for alerts)."""
        return (ScrapingSession.query
                .filter(ScrapingSession.status == "failed")
                .filter(ScrapingSession.created_at >= since)
                .order_by(ScrapingSession.created_at.desc())
                .limit(limit)
                .all())

    @staticmethod
    def get_by_date(target_date: date, platform: str = None) -> list[ScrapingSession]:
        """
        Get all sessions for a specific date.
        
        Args:
            target_date: Date to filter by
            platform: Optional platform filter (not directly on session, 
                      but can be inferred from associated comments)
            
        Returns:
            list[ScrapingSession]: List of sessions for that date
        """
        # Create datetime range for the target date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        query = ScrapingSession.query.filter(
            ScrapingSession.created_at >= start_datetime,
            ScrapingSession.created_at <= end_datetime
        )
        
        # Note: Platform filter would require joining with comments table
        # For simplicity, we filter sessions that have comments with that platform
        if platform:
            from api.models.comment_model import Comment
            query = query.join(Comment, ScrapingSession.session_id == Comment.scraping_session_id)
            query = query.filter(Comment.platform == platform)
            query = query.distinct()
        
        return query.order_by(ScrapingSession.created_at.desc()).all()
    
    @staticmethod
    def get_daily_summary(target_date: date, platform: str = None) -> dict:
        """
        Get aggregated summary for a specific date.
        
        Args:
            target_date: Date to filter by
            platform: Optional platform filter
            
        Returns:
            dict: Aggregated statistics for the day
        """
        sessions = ScrapingSessionRepository.get_by_date(target_date, platform)
        
        if not sessions:
            return {
                "date": target_date.isoformat(),
                "total_sessions": 0,
                "sessions_by_status": {"pending": 0, "completed": 0, "failed": 0},
                "total_posts_fetched": 0,
                "total_comments_inserted": 0,
                "total_expected_comments": 0,
                "comments_ratio": None,
                "duration_stats": None,
                "errors": []
            }
        
        # Aggregate by status
        status_counts = {"pending": 0, "completed": 0, "failed": 0}
        total_posts = 0
        total_comments_inserted = 0
        durations = []
        errors = []
        
        for session in sessions:
            status_counts[session.status] = status_counts.get(session.status, 0) + 1
            total_posts += session.posts_fetched or 0
            total_comments_inserted += session.comments_inserted or 0
            
            # Track duration for completed sessions
            if session.status == "completed" and session.created_at and session.completed_at:
                duration_seconds = (session.completed_at - session.created_at).total_seconds()
                durations.append(duration_seconds)
            
            # Track errors
            if session.status == "failed" and session.error_message:
                errors.append({
                    "session_id": session.session_id,
                    "error": session.error_message[:200]  # Truncate long errors
                })
        
        # Calculate expected comments from posts for these sessions
        total_expected_comments = ScrapingSessionRepository._get_expected_comments_for_sessions(
            [s.session_id for s in sessions], platform
        )
        
        # Calculate ratio
        comments_ratio = None
        if total_expected_comments > 0:
            comments_ratio = round(total_comments_inserted / total_expected_comments, 4)
        
        # Duration stats
        duration_stats = None
        if durations:
            duration_stats = {
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "avg_seconds": round(sum(durations) / len(durations), 2),
                "min_formatted": _format_duration(min(durations)),
                "max_formatted": _format_duration(max(durations)),
                "avg_formatted": _format_duration(sum(durations) / len(durations))
            }
        
        return {
            "date": target_date.isoformat(),
            "platform_filter": platform,
            "total_sessions": len(sessions),
            "sessions_by_status": status_counts,
            "total_posts_fetched": total_posts,
            "total_comments_inserted": total_comments_inserted,
            "total_expected_comments": total_expected_comments,
            "comments_ratio": comments_ratio,
            "duration_stats": duration_stats,
            "errors": errors
        }
    
    @staticmethod
    def _get_expected_comments_for_sessions(session_ids: list[str], platform: str = None) -> int:
        """
        Calculate total expected comments from posts associated with sessions.
        
        This queries the posts that were fetched during these sessions by looking
        at the posts recorded yesterday (as per the scraping logic).
        
        Args:
            session_ids: List of session UUIDs
            platform: Optional platform filter
            
        Returns:
            int: Total expected comment count
        """
        if not session_ids:
            return 0
        
        from sqlalchemy import cast, String
        from api.models.comment_model import Comment
        from api.models.post_model import PostMV
        
        # Build subquery to get unique (page_id, platform, post_id) from comments
        subquery_stmt = (db.session.query(
            Comment.page_id, 
            Comment.platform, 
            Comment.post_id
        ).filter(Comment.scraping_session_id.in_(session_ids))
         .distinct())
        
        if platform:
            subquery_stmt = subquery_stmt.filter(Comment.platform == platform)
        
        # Create a single subquery alias to reuse
        posts_subquery = subquery_stmt.subquery()
        
        # Join with posts_mv to get expected comment counts
        # Cast page_id to String to handle potential UUID vs varchar mismatch
        result = (db.session.query(func.coalesce(func.sum(PostMV.comments), 0))
                  .select_from(posts_subquery)
                  .join(PostMV, 
                        db.and_(
                            cast(PostMV.page_id, String) == posts_subquery.c.page_id,
                            PostMV.platform == posts_subquery.c.platform,
                            PostMV.post_id == posts_subquery.c.post_id
                        ))
                  .scalar())
        
        return result or 0


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
