# Business workflows for scraping service.
import uuid
from datetime import datetime
from api.repositories.comment_repository import CommentRepository
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.repositories.post_repository import PostRepository
from api.repositories.scraping_post_result_repository import ScrapingPostResultRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.page_repository import PageRepository
from api.repositories.scraping_profile_result_repository import ScrapingProfileResultRepository
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class

# The own-scraper's profile-info flow (see api/docs/scraping_profiles.md)
# only exists for Instagram today -- run_api_docker.sh explicitly refuses
# MODE=profile for any other platform. Gate it here too rather than
# silently accepting and mis-storing data if that ever changes upstream
# without this being updated to match.
PROFILE_SUPPORTED_PLATFORMS = ("instagram",)


@instrument_service_class
class ScrapingService:
    """Service for managing scraping operations."""
    
    @staticmethod
    def get_profiles_for_scraping(platform: str = None) -> dict:
        """
        Get all page URLs for active entities (to_scrape=True).
        
        Args:
            platform: Optional platform filter (instagram, facebook, x, tiktok, linkedin, youtube)
            
        Returns:
            dict: {
                "profiles": list[dict],  # [{name, link, platform, entity_id, entity_name}, ...]
                "count": int,
                "platform": str | None
            }
        """
        # Get pages for active entities
        pages = PageRepository.get_active_pages_by_platform(platform)
        
        # Format response
        profiles = [
            {
                "name": page.name,
                "url": page.link,
                "platform": page.platform,
                "entity_id": page.entity_id,
                "entity_name": page.entity.name if page.entity else None,
            }
            for page in pages
        ]
        
        return {
            "profiles": profiles,
            "count": len(profiles),
            "platform": platform if platform else "all"
        }
    
    @staticmethod
    def get_failed_profiles_for_scraping(platform: str = None, limit: int = None) -> dict:
        """
        Get profiles that failed scraping validation from yesterday 10pm UTC until now.
        
        Args:
            platform: Optional platform filter (instagram, facebook, x, tiktok, linkedin, youtube)
            limit: Optional integer limit for number of profiles returned
            
        Returns:
            dict: {
                "profiles": list[dict],  # [{name, url, platform, entity_id, entity_name}, ...]
                "count": int,
                "platform": str,
                "scraping_issues": list[str]  # List of detected issues
            }
        """
        # Step 1: Get failed page IDs from yesterday 10pm until now
        failed_pages = PageHistoryRepository.get_failed_pages_for_today()
        
        # Step 2: Extract page IDs
        page_ids = [failed_page["page_id"] for failed_page in failed_pages]
        
        # Step 3: Handle empty case
        if not page_ids:
            return {
                "profiles": [],
                "count": 0,
                "platform": platform if platform else "all",
                "scraping_issues": []
            }
        
        # Step 4: Fetch full page details with entity filtering
        pages = PageRepository.get_pages_by_ids(page_ids, platform)
        
        # Step 5: Format response and collect unique scraping issues
        profiles = []
        scraping_issues = set()
        
        for page in pages:
            profile = {
                "name": page.name,
                "url": page.link,
                "platform": page.platform,
                "entity_id": page.entity_id,
                "entity_name": page.entity.name if page.entity else None,
            }
            profiles.append(profile)
            
            # Collect unique scraping issues
            failed_page_info = next(
                (fp for fp in failed_pages if fp["page_id"] == page.uuid),
                None
            )
            if failed_page_info:
                for key in failed_page_info["missing_keys"]:
                    scraping_issues.add(key)
        
        if limit and limit > 0:
            profiles = profiles[:limit]
        
        return {
            "profiles": profiles,
            "count": len(profiles),
            "platform": platform if platform else "all",
            "scraping_issues": sorted(list(scraping_issues))  # Sort for consistent output
        }
    
    @staticmethod
    def fetch_posts_for_scraping(platform: str = None, 
                                  start_date: str = None, 
                                  end_date: str = None,
                                  recorded_start_date: str = None,
                                  recorded_end_date: str = None) -> dict:
        """
        Fetch posts matching filters and create scraping session.
        Only returns posts that have not already been scraped today
        (i.e., no comments inserted today and no ScrapingPostResult today).
        
        Args:
            platform: Optional platform filter
            start_date: Optional creation start date (ISO format)
            end_date: Optional creation end date (ISO format)
            recorded_start_date: Optional recorded_at start date (ISO format)
            recorded_end_date: Optional recorded_at end date (ISO format)
            
        Returns:
            dict: {
                "session_id": str,
                "posts": list[dict],
                "count": int,
                "total_available": int
            }
        """
        from datetime import timedelta, timezone
        from api.models.post_model import PostMV
        from api.models.comment_model import Comment
        from api import db

        today = datetime.utcnow().date()

        def parse_iso_utc(date_str: str) -> datetime:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        # Build base query - fetch active posts
        query = PostMV.query
        
        # Apply platform filter
        if platform:
            query = query.filter_by(platform=platform)
        
        # Apply date filters (on post creation date, created_at)
        if start_date:
            query = query.filter(PostMV.created_at >= parse_iso_utc(start_date))
        
        if end_date:
            query = query.filter(PostMV.created_at <= parse_iso_utc(end_date))

        # Apply snapshot recorded_at date filters
        if recorded_start_date:
            query = query.filter(PostMV.recorded_at >= parse_iso_utc(recorded_start_date))

        if recorded_end_date:
            query = query.filter(PostMV.recorded_at <= parse_iso_utc(recorded_end_date))
        
        # Get total count before applying the scraped-today filter
        total_available = query.count()
        
        # Filter out posts that already have comments inserted today
        # A post is considered "scraped today" if it has at least one comment
        # with recorded_at within today's date range, or a ScrapingPostResult row today.
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        
        # Exclude posts that are already done for today.
        from sqlalchemy import exists, and_, cast, String
        from api.models.scraping_post_result_model import ScrapingPostResult

        comment_exists = exists().where(
            and_(
                cast(Comment.page_id, String) == cast(PostMV.page_id, String),
                Comment.platform == PostMV.platform,
                Comment.post_id == PostMV.post_id,
                Comment.recorded_at >= today_start,
                Comment.recorded_at < today_end
            )
        )

        result_exists = exists().where(
            and_(
                cast(ScrapingPostResult.page_id, String) == cast(PostMV.page_id, String),
                ScrapingPostResult.platform == PostMV.platform,
                ScrapingPostResult.post_id == PostMV.post_id,
                ScrapingPostResult.scraped_at >= today_start,
                ScrapingPostResult.scraped_at < today_end
            )
        )

        query = query.filter(~comment_exists, ~result_exists)
        
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
                "comment_timestamp": datetime.utcfromtimestamp(comment["timestamp"]),  # Unix (UTC) -> naive UTC datetime
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

        # Parse date or default to today (UTC, to match stored timestamps)
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = datetime.utcnow().date()

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

        # Parse date or default to today (UTC, to match stored timestamps)
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = datetime.utcnow().date()

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
    def get_today_scraping_status(platform: str = None, 
                                  target_date: str = None, 
                                  start_date: str = None,
                                  recorded_start_date: str = None,
                                  recorded_end_date: str = None) -> dict:
        """
        Get the scraping status of posts scheduled for a specific date.
        Categorizes posts into scraped (already scraped on target date)
        and pending (not yet scraped on target date).
        
        Args:
            platform: Optional platform filter
            target_date: Optional date in ISO format (YYYY-MM-DD). Defaults to today.
            start_date: Optional start date (ISO format) to filter post creation date.
            recorded_start_date: Optional recorded_at start date (ISO format).
            recorded_end_date: Optional recorded_at end date (ISO format).
            
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
        from datetime import date as date_type, timedelta, timezone
        from api.models.post_model import PostMV
        from api.models.comment_model import Comment
        from api import db
        from sqlalchemy import func

        def parse_iso_utc(date_str: str) -> datetime:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        
        # Parse date or default to today (UTC, to match stored timestamps)
        if target_date:
            parsed_date = date_type.fromisoformat(target_date)
        else:
            parsed_date = datetime.utcnow().date()
        
        # Target date's range (when scraping happened)
        target_date_start = datetime.combine(parsed_date, datetime.min.time())
        target_date_end = datetime.combine(parsed_date + timedelta(days=1), datetime.min.time())
        
        # Query active posts
        posts_query = PostMV.query
        if platform:
            posts_query = posts_query.filter_by(platform=platform)

        if start_date:
            posts_query = posts_query.filter(PostMV.created_at >= parse_iso_utc(start_date))

        if recorded_start_date:
            posts_query = posts_query.filter(PostMV.recorded_at >= parse_iso_utc(recorded_start_date))

        if recorded_end_date:
            posts_query = posts_query.filter(PostMV.recorded_at <= parse_iso_utc(recorded_end_date))

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

    # ── Profile-info flow ──────────────────────────────────────────────
    # Counterpart to fetch_posts_for_scraping/insert_comment_batch above,
    # for the own-scraper's *profile* pass (core/profile_api_flow.py on the
    # scraper side) rather than its comment pass. See
    # api/docs/scraping_profiles.md for the full contract this was built
    # against -- the client-side code (core/api_client.py's
    # fetch_profiles/insert_profiles) was read directly off the deployed
    # scraper rather than guessed, since these routes previously didn't
    # exist at all and every call the scraper made 404'd.

    @staticmethod
    def fetch_profiles_for_scraping(
        platform: str,
        start_date: str = None,
        recorded_start_date: str = None,
        recorded_end_date: str = None,
    ) -> dict:
        """
        Fetch accounts whose profile info is due for a refresh, and create
        a scraping session. The source rows are `pages` (not posts), and
        "already handled today" is tracked via ScrapingProfileResult rather
        than Comment/ScrapingPostResult.

        `start_date`/`recorded_start_date`/`recorded_end_date` are accepted
        for parity with the client, which always sends them (mirroring
        fetch_posts's contract) -- but a page has no natural per-row
        creation/content date the way a post does, so they aren't used to
        filter here. Only `platform` and "not already handled today" are.

        Returns:
            dict: {
                "session_id": str,
                "profiles": list[{"account_id": str, "page_id": str, "url": str}],
                "count": int,
                "total_available": int
            }
        """
        if not platform:
            raise ValueError("platform is required to fetch profiles for scraping.")
        if platform not in PROFILE_SUPPORTED_PLATFORMS:
            raise ValueError(
                f"Profile scraping isn't supported for platform '{platform}' yet "
                f"(only {', '.join(PROFILE_SUPPORTED_PLATFORMS)} today)."
            )

        from datetime import timedelta

        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

        pages = PageRepository.get_active_by_platform(platform)
        total_available = len(pages)

        done_page_ids = ScrapingProfileResultRepository.get_scraped_page_ids_in_range(
            start_dt=today_start, end_dt=today_end, platform=platform
        )
        pending_pages = [p for p in pages if str(p.uuid) not in done_page_ids]

        session = ScrapingSessionRepository.create(posts_fetched=len(pending_pages))

        # account_id == page_id today (see ScrapingProfileResult's module
        # docstring for why): this schema has no separate accounts table.
        profiles = [
            {"account_id": str(p.uuid), "page_id": str(p.uuid), "url": p.link}
            for p in pending_pages
        ]

        return {
            "session_id": session.session_id,
            "profiles": profiles,
            "count": len(profiles),
            "total_available": total_available,
        }

    @staticmethod
    def validate_profile_data(profile: dict) -> tuple[bool, str]:
        """
        Validate a single scraped profile record's routing fields.

        Args:
            profile: Profile dictionary (routing keys + whatever the
                     scraper captured)

        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = ["page_id", "platform", "account_id"]
        for field in required_fields:
            if field not in profile or profile[field] is None:
                return False, f"missing required field '{field}'"

        if profile["platform"] not in PROFILE_SUPPORTED_PLATFORMS:
            return False, (
                f"unsupported platform '{profile['platform']}' for profile-info "
                f"(only {', '.join(PROFILE_SUPPORTED_PLATFORMS)} today)"
            )

        return True, ""

    @staticmethod
    def insert_profile_batch(
        profiles_data: list[dict],
        session_id: str = None,
        profile_results: list[dict] = None,
    ) -> dict:
        """
        Validate and write a batch of scraped profile records into
        pages_history, and record ScrapingProfileResult rows for every
        account actually visited this run -- including ones only listed in
        `profile_results` (visited but unscrapeable), so they're marked
        done rather than re-served on the next fetch. Mirrors
        insert_comment_batch's shape and its "reject the whole batch on the
        first invalid entry" behavior (the external scraper already
        defensively coerces null/missing fields before sending, precisely
        because it expects that from this backend).

        Args:
            profiles_data: List of profile dictionaries (may be empty --
                           e.g. a batch that was entirely unscrapeable)
            session_id: Optional session ID to associate results with
            profile_results: Optional list of {page_id, platform, account_id}
                              for every account visited this batch, scraped
                              or not

        Returns:
            dict: {"inserted": int, "skipped": int, "session_id": str, "total": int}
        """
        for idx, profile in enumerate(profiles_data):
            is_valid, error_msg = ScrapingService.validate_profile_data(profile)
            if not is_valid:
                raise ValueError(f"Validation failed at profile index {idx}: {error_msg}")

        inserted = 0
        processed_keys = set()

        for profile in profiles_data:
            page_id_raw = profile["page_id"]
            platform = profile["platform"]

            # page_id arrives as a plain string (it came off JSON), but
            # PageHistory.page_id is a UUID-typed column -- pass a real
            # uuid.UUID rather than relying on a given driver being lenient
            # about a bare string (SQLite's generic UUID emulation isn't;
            # this surfaced as a test failure before it could surface as a
            # production one). A malformed id fails this one profile's
            # validation cleanly rather than however the DB layer would
            # have reported a bad bind parameter.
            try:
                page_id = uuid.UUID(str(page_id_raw))
            except (ValueError, AttributeError, TypeError):
                raise ValueError(
                    f"profile for page_id={page_id_raw!r} is not a valid UUID"
                )

            # Everything scraped is kept in pages_history.data as-is, minus
            # the routing keys -- the scraper's own field names (followers,
            # biography, profile_image_link, ...) already match what
            # PageHistoryRepository's Instagram case-builders and
            # scrape_validation_service.PROFILE_FIELD_MAP expect, so no
            # remapping is needed here, only stripping the envelope.
            data = {
                k: v for k, v in profile.items()
                if k not in ("page_id", "platform", "account_id")
            }

            PageHistoryRepository.create(
                page_id=page_id,
                data=data,
                source="own_scraper",
                source_meta={"cost_usd": 0.0},
                commit=False,
            )
            inserted += 1
            processed_keys.add((str(page_id_raw), platform))

        if profile_results:
            for pr in profile_results:
                page_id = pr["page_id"]
                platform = pr["platform"]
                account_id = pr.get("account_id") or page_id
                ScrapingProfileResultRepository.record(
                    page_id=page_id,
                    platform=platform,
                    account_id=account_id,
                    profile_inserted=(str(page_id), platform) in processed_keys,
                    scraping_session_id=session_id,
                    commit=False,
                )

        from api.models.comment_model import db
        db.session.commit()

        return {
            "inserted": inserted,
            "skipped": 0,
            "session_id": session_id,
            "total": inserted,
        }

