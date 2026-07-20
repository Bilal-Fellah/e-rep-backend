# Business workflows for scraping service.
from datetime import datetime
from api.repositories.comment_repository import CommentRepository
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.repositories.post_repository import PostRepository
from api.repositories.scraping_post_result_repository import ScrapingPostResultRepository
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class


@instrument_service_class
class ScrapingService:
    """Service for managing scraping operations."""
    
    @staticmethod
    def fetch_posts_for_scraping(platform: str = None, 
                                  start_date: str = None, 
                                  end_date: str = None) -> dict:
        """
        Fetch posts matching filters and create scraping session.
        Only returns posts that were recorded in yesterday's snapshot
        and have not already been scraped today (i.e., no comments inserted today).
        
        Args:
            platform: Optional platform filter
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            
        Returns:
            dict: {
                "session_id": str,
                "posts": list[dict],
                "count": int,
                "total_available": int
            }
        """
        from datetime import date, timedelta
        from api.models.post_model import PostMV
        from api.models.comment_model import Comment
        from api import db
        
        # Calculate yesterday's date range (midnight to midnight)
        today = date.today()
        yesterday_start = datetime.combine(today - timedelta(days=1), datetime.min.time())
        yesterday_end = datetime.combine(today, datetime.min.time())

        print(f"Fetching posts recorded between {yesterday_start} and {yesterday_end}")
        
        # Build query - only posts recorded yesterday
        query = PostMV.query.filter(
            PostMV.recorded_at >= yesterday_start,
            PostMV.recorded_at < yesterday_end
        )
        
        # Apply platform filter
        if platform:
            query = query.filter_by(platform=platform)
        
        # Apply date filters (on post creation date, not recorded_at)
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(PostMV.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(PostMV.created_at <= end_dt)
        
        # Get total count before applying the scraped-today filter
        total_available = query.count()
        
        # Filter out posts that already have comments inserted today
        # A post is considered "scraped today" if it has at least one comment
        # with recorded_at within today's date range
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        
        # Exclude posts that are in the scraped_today subquery
        # Using ~exists() for better performance with large datasets
        # Note: Cast page_id to String to handle UUID vs VARCHAR type mismatch
        from sqlalchemy import exists, and_, cast, String
        
        exists_clause = exists().where(
            and_(
                cast(Comment.page_id, String) == cast(PostMV.page_id, String),
                Comment.platform == PostMV.platform,
                Comment.post_id == PostMV.post_id,
                Comment.recorded_at >= today_start,
                Comment.recorded_at < today_end
            )
        )
        
        if platform:
            exists_clause = exists().where(
                and_(
                    cast(Comment.page_id, String) == cast(PostMV.page_id, String),
                    Comment.platform == PostMV.platform,
                    Comment.post_id == PostMV.post_id,
                    Comment.recorded_at >= today_start,
                    Comment.recorded_at < today_end,
                    Comment.platform == platform
                )
            )
        
        query = query.filter(~exists_clause)
        
        # Fetch posts
        posts = query.all()
        posts_data = [post.to_scraping_dict() for post in posts]
        
        # Create scraping session
        session = ScrapingSessionRepository.create(posts_fetched=len(posts_data))
        
        return {
            "session_id": session.session_id,
            "posts": posts_data,
            "count": len(posts_data),
            "total_available": total_available
        }
    
    @staticmethod
    def insert_comment_batch(
        comments_data: list[dict],
        session_id: str = None,
        post_results: list[dict] = None,
    ) -> dict:
        """
        Validate and insert comment batch atomically.
        An empty list is accepted (e.g. for posts with no comments); in that
        case the call succeeds with inserted=0, skipped=0.

        To mark zero-comment posts as done, pass their identity in
        ``post_results``:

            post_results = [
                {"page_id": "...", "platform": "instagram", "post_id": "..."}
            ]

        For each post in ``post_results`` (and for every post that appears in
        ``comments_data``) a ``ScrapingPostResult`` row is written so the
        today-status endpoint can distinguish "done with 0 comments" from
        "not yet scraped".

        Args:
            comments_data: List of comment dictionaries (may be empty)
            session_id: Optional session ID to associate comments with
            post_results: Optional list of {page_id, platform, post_id} dicts
                          for posts that were scraped but had no comments.

        Returns:
            dict: {
                "inserted": int,
                "skipped": int,
                "session_id": str
            }
        """
        # Validate all comments first
        for idx, comment in enumerate(comments_data):
            is_valid, error_msg = ScrapingService.validate_comment_data(comment)
            if not is_valid:
                raise ValueError(f"Validation failed at comment index {idx}: {error_msg}")

        # Transform comments to match database schema
        # The external service sends: id, username, timestamp (Unix), parent_id
        # We need: comment_id, author_username, comment_timestamp (datetime), parent_comment_id
        transformed_comments = []
        for comment in comments_data:
            transformed = {
                "page_id": comment["page_id"],
                "platform": comment["platform"],
                "post_id": comment["post_id"],
                "comment_id": comment["id"],  # Map id -> comment_id
                "text": comment["text"],
                "author_username": comment["username"],  # Map username -> author_username
                "author_profile_url": comment.get("author_profile_url"),  # Optional
                "comment_timestamp": datetime.fromtimestamp(comment["timestamp"]),  # Convert Unix to datetime
                "likes_count": comment.get("likes", 0),
                "replies_count": comment.get("replies_count", 0),
                "parent_comment_id": comment.get("parent_id"),  # Map parent_id -> parent_comment_id
                "scraping_session_id": session_id,
                "extra_data": {
                    "is_reply": comment.get("is_reply", False)
                }
            }
            transformed_comments.append(transformed)

        # Insert comments (skips duplicates)
        inserted, skipped = CommentRepository.bulk_create(transformed_comments, commit=False)

        # Update session if provided
        if session_id:
            ScrapingSessionRepository.increment_comments(session_id, inserted, commit=False)

        # ------------------------------------------------------------------ #
        # Record per-post scraping outcomes in ScrapingPostResult.
        #
        # Build a mapping: (page_id, platform, post_id) -> inserted_count
        # from the comment batch so we know how many comments each post got.
        # ------------------------------------------------------------------ #
        post_comment_counts: dict[tuple, int] = {}
        for comment in comments_data:
            key = (comment["page_id"], comment["platform"], comment["post_id"])
            post_comment_counts[key] = post_comment_counts.get(key, 0) + 1

        # Posts explicitly declared with 0 comments
        if post_results:
            for pr in post_results:
                key = (pr["page_id"], pr["platform"], pr["post_id"])
                if key not in post_comment_counts:
                    post_comment_counts[key] = 0

        # Write / update a ScrapingPostResult row for every processed post
        for (page_id, platform, post_id), count in post_comment_counts.items():
            ScrapingPostResultRepository.record(
                page_id=page_id,
                platform=platform,
                post_id=post_id,
                comments_count=count,
                scraping_session_id=session_id,
                commit=False,
            )

        # Commit everything in one transaction
        from api.models.comment_model import db
        db.session.commit()

        return {
            "inserted": inserted,
            "skipped": skipped,
            "session_id": session_id
        }
    
    @staticmethod
    def validate_comment_data(comment: dict) -> tuple[bool, str]:
        """
        Validate a single comment's required fields.
        
        Args:
            comment: Comment dictionary
            
        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = [
            "page_id",
            "platform",
            "post_id",
            "id",  # External service sends 'id', not 'comment_id'
            "text",
            "username",  # External service sends 'username', not 'author_username'
            "timestamp"  # External service sends 'timestamp', not 'comment_timestamp'
        ]
        
        for field in required_fields:
            if field not in comment or comment[field] is None:
                return False, f"missing required field '{field}'"
        
        # Validate data types
        if not isinstance(comment["text"], str):
            return False, "field 'text' must be a string"
        
        if not isinstance(comment["username"], str):
            return False, "field 'username' must be a string"
        
        if not isinstance(comment["timestamp"], (int, float)):
            return False, "field 'timestamp' must be a number"
        
        if "likes" in comment and not isinstance(comment["likes"], (int, float)):
            return False, "field 'likes' must be a number"
        
        return True, ""
    
    @staticmethod
    def get_session_details(session_id: str) -> dict | None:
        """
        Retrieve complete session information.
        
        Args:
            session_id: Session UUID
            
        Returns:
            dict | None: {
                "session_id": str,
                "created_at": str,
                "completed_at": str | None,
                "posts_fetched": int,
                "comments_inserted": int,
                "status": str,
                "error_message": str | None
            }
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "created_at": iso_utc(session.created_at),
            "completed_at": iso_utc(session.completed_at),
            "posts_fetched": session.posts_fetched,
            "comments_inserted": session.comments_inserted,
            "status": session.status,
            "error_message": session.error_message
        }
    
    @staticmethod
    def complete_scraping_session(session_id: str) -> dict | None:
        """
        Mark a scraping session as completed.
        Only a session in 'pending' state can be completed.
        
        Args:
            session_id: Session UUID
            
        Returns:
            dict | None: {
                "session_id": str,
                "status": "completed",
                "completed_at": str,
                "posts_fetched": int,
                "comments_inserted": int
            }
            None if session not found.
            
        Raises:
            ValueError: If the session is already completed or failed.
        """
        session = ScrapingSessionRepository.get_by_id(session_id)
        
        if not session:
            return None
        
        if session.status != "pending":
            raise ValueError(
                f"Session '{session_id}' cannot be completed: "
                f"current status is '{session.status}'"
            )
        
        updated = ScrapingSessionRepository.complete_session(session_id)
        
        return {
            "session_id": updated.session_id,
            "status": updated.status,
            "completed_at": iso_utc(updated.completed_at),
            "posts_fetched": updated.posts_fetched,
            "comments_inserted": updated.comments_inserted
        }
    
    @staticmethod
    def get_daily_summary(target_date: str = None, platform: str = None) -> dict:
        """
        Get aggregated scraping summary for a specific date.
        
        Args:
            target_date: Date in ISO format (YYYY-MM-DD). Defaults to today.
            platform: Optional platform filter
            
        Returns:
            dict: {
                "date": str,
                "platform_filter": str | None,
                "total_sessions": int,
                "sessions_by_status": dict,
                "total_posts_fetched": int,
                "total_comments_inserted": int,
                "total_expected_comments": int,
                "comments_ratio": float | None,
                "duration_stats": dict | None,
                "errors": list
            }
        """
        from datetime import date as date_type
        
        # Parse date or default to today
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = date_type.today()
        
        return ScrapingSessionRepository.get_daily_summary(parsed_date, platform)
    
    @staticmethod
    def get_sessions_for_date(target_date: str = None, platform: str = None) -> list[dict]:
        """
        Get all scraping sessions for a specific date.
        
        Args:
            target_date: Date in ISO format (YYYY-MM-DD). Defaults to today.
            platform: Optional platform filter
            
        Returns:
            list[dict]: List of session details
        """
        from datetime import date as date_type
        
        # Parse date or default to today
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = date_type.today()
        
        sessions = ScrapingSessionRepository.get_by_date(parsed_date, platform)
        
        result = []
        for session in sessions:
            session_dict = {
                "session_id": session.session_id,
                "created_at": iso_utc(session.created_at),
                "completed_at": iso_utc(session.completed_at),
                "posts_fetched": session.posts_fetched,
                "comments_inserted": session.comments_inserted,
                "status": session.status,
                "error_message": session.error_message
            }
            
            # Calculate duration for completed sessions
            if session.status == "completed" and session.created_at and session.completed_at:
                duration_seconds = (session.completed_at - session.created_at).total_seconds()
                session_dict["duration_seconds"] = round(duration_seconds, 2)
            
            result.append(session_dict)
        
        return result

    @staticmethod
    def get_today_scraping_status(platform: str = None, target_date: str = None, start_date: str = None) -> dict:
        """
        Get the scraping status of posts scheduled for a specific date.
        Categorizes posts scheduled for that date into scraped (already scraped today)
        and pending (scheduled but not yet scraped).
        
        Args:
            platform: Optional platform filter
            target_date: Optional date in ISO format (YYYY-MM-DD). Defaults to today.
            start_date: Optional start date (ISO format) to filter post creation date.
            
        Returns:
            dict: {
                "date": str,
                "platform_filter": str | None,
                "start_date_filter": str | None,
                "scraped_count": int,
                "pending_count": int,
                "total_count": int,
                "scraped_posts": list[dict],
                "pending_posts": list[dict]
            }
        """
        from datetime import date as date_type, timedelta
        from api.models.post_model import PostMV
        from api.models.comment_model import Comment
        from api import db
        from sqlalchemy import func
        
        # Parse date or default to today
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = date_type.today()
            
        # Yesterday's range (snapshot date for scheduled posts)
        yesterday_start = datetime.combine(parsed_date - timedelta(days=1), datetime.min.time())
        yesterday_end = datetime.combine(parsed_date, datetime.min.time())
        
        # Target date's range (when scraping happened)
        target_date_start = datetime.combine(parsed_date, datetime.min.time())
        target_date_end = datetime.combine(parsed_date + timedelta(days=1), datetime.min.time())
        
        # Query posts scheduled for target_date
        posts_query = PostMV.query.filter(
            PostMV.recorded_at >= yesterday_start,
            PostMV.recorded_at < yesterday_end
        )
        if platform:
            posts_query = posts_query.filter_by(platform=platform)

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            posts_query = posts_query.filter(PostMV.created_at >= start_dt)

        posts = posts_query.all()

        # Look up which posts already have a ScrapingPostResult row recorded
        # on the target date — these are considered "done" regardless of whether
        # they had 0 or more comments.
        scraped_keys = ScrapingPostResultRepository.get_scraped_post_keys_in_range(
            start_dt=target_date_start,
            end_dt=target_date_end,
            platform=platform,
        )

        # Also fetch actual comment counts for posts that were scraped, so we
        # can report accurate scraped_comments_count in the response.
        comment_counts_query = db.session.query(
            Comment.page_id,
            Comment.platform,
            Comment.post_id,
            func.count(Comment.id).label('count')
        ).filter(
            Comment.recorded_at >= target_date_start,
            Comment.recorded_at < target_date_end
        )
        if platform:
            comment_counts_query = comment_counts_query.filter(Comment.platform == platform)

        comment_counts = comment_counts_query.group_by(
            Comment.page_id,
            Comment.platform,
            Comment.post_id
        ).all()

        counts_lookup = {}
        for page_id, platform_val, post_id, count in comment_counts:
            counts_lookup[(str(page_id), platform_val, post_id)] = count

        scraped_posts = []
        pending_posts = []

        for post in posts:
            key = (str(post.page_id), post.platform, post.post_id)
            comments_got = counts_lookup.get(key, 0)

            post_info = {
                "page_id": post.page_id,
                "platform": post.platform,
                "post_id": post.post_id,
                "url": post.url,
                # "caption": post.caption,
                "expected_comments": post.comments,
                "scraped_comments_count": comments_got,
                "recorded_at": post.recorded_at.isoformat() if post.recorded_at else None,
                "created_at": post.created_at.isoformat() if post.created_at else None
            }

            # A post is done when a ScrapingPostResult row exists for today,
            # even if comments_got == 0 (post was scraped but had no comments).
            # A post with no ScrapingPostResult row is still pending.
            if key in scraped_keys:
                scraped_posts.append(post_info)
            else:
                pending_posts.append(post_info)

        return {
            "date": parsed_date.isoformat(),
            "platform_filter": platform,
            "start_date_filter": start_date,
            "scraped_count": len(scraped_posts),
            "pending_count": len(pending_posts),
            "total_count": len(posts),
            "scraped_posts": scraped_posts,
            "pending_posts": pending_posts
        }

