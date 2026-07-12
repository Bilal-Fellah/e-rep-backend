# Business workflows for scraping service.
from datetime import datetime
from api.repositories.comment_repository import CommentRepository
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.repositories.post_repository import PostRepository
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
        Only returns posts that were recorded in yesterday's snapshot.
        
        Args:
            platform: Optional platform filter
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            
        Returns:
            dict: {
                "session_id": str,
                "posts": list[dict],
                "count": int
            }
        """
        from datetime import date, timedelta
        from api.models.post_model import PostMV
        
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
        
        # Fetch posts
        posts = query.all()
        posts_data = [post.to_scraping_dict() for post in posts]
        
        # Create scraping session
        session = ScrapingSessionRepository.create(posts_fetched=len(posts_data))
        
        return {
            "session_id": session.session_id,
            "posts": posts_data,
            "count": len(posts_data)
        }
    
    @staticmethod
    def insert_comment_batch(comments_data: list[dict], 
                            session_id: str = None) -> dict:
        """
        Validate and insert comment batch atomically.
        
        Args:
            comments_data: List of comment dictionaries
            session_id: Optional session ID to associate comments with
            
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
        
        # Commit transaction
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
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "posts_fetched": session.posts_fetched,
            "comments_inserted": session.comments_inserted,
            "status": session.status,
            "error_message": session.error_message
        }
