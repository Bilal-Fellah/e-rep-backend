# Route handlers for scraping endpoints.
from flask import Blueprint, request
from sqlalchemy.exc import SQLAlchemyError

from api.routes.main import (
    error_response,
    success_response,
    db_error_response,
    server_error_response,
    register_blueprint_error_handlers,
    log_route_error,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH
)
from api.services.scraping_service import ScrapingService
from api.services.scraper_credential_service import ScraperCredentialError, ScraperCredentialService
from api.services.scrape_trigger_service import ScrapeTriggerError, ScrapeTriggerService
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.utils.api_key_auth import require_api_key
from api.utils.permissions import require_auth
from api.models.comment_model import db
# Import new model so Alembic/Flask-Migrate picks it up for migrations
from api.models.scraping_post_result_model import ScrapingPostResult  # noqa: F401
from api.models.scraper_credential_model import ScraperCredential  # noqa: F401
from api.models.scrape_trigger_request_model import ScrapeTriggerRequest  # noqa: F401


scraping_bp = Blueprint("scraping", __name__, url_prefix="/api/scraping")
register_blueprint_error_handlers(scraping_bp)


@scraping_bp.route("/profiles", methods=["GET"])
@require_api_key
def get_profiles():
    """
    Get all page URLs for active entities (to_scrape=True).
    Used by scrapers to know which profiles to scrape.
    
    Query Parameters:
        - platform (optional): Filter by platform (instagram, facebook, x, tiktok, linkedin, youtube)
    
    Returns:
        200: {
            "success": true,
            "data": {
                "profiles": list[dict],  # [{name, link, platform, entity_id, entity_name}, ...]
                "count": int,
                "platform": str
            }
        }
        400: Invalid query parameters
        401: Missing or invalid API key
        500: Database error
    
    Example:
        GET /api/scraping/profiles?platform=instagram
        
        Response:
        {
            "success": true,
            "data": {
                "profiles": [
                    {
                        "name": "company_instagram",
                        "link": "https://instagram.com/company",
                        "platform": "instagram",
                        "entity_id": 1,
                        "entity_name": "Company Name"
                    }
                ],
                "count": 1,
                "platform": "instagram"
            }
        }
    """
    try:
        # Extract query parameters
        platform = request.args.get("platform")
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Get profiles
        result = ScrapingService.get_profiles_for_scraping(platform=platform)
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during profile fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during profile fetch")
        return server_error_response(500)


@scraping_bp.route("/apify_profile_scraping", methods=["GET"])
@require_api_key
def get_apify_profiles():
    """
    Get profiles whose most recent scrape came back incomplete, from
    yesterday 10pm UTC until now (see PageHistoryRepository.validate_data_structure
    for exactly what "incomplete" checks). This is a general validation
    result, not an Apify-specific one -- the Apify fallback pipeline is
    today's only consumer, but it decides on its own whether/when that's
    worth a paid retry; this endpoint just reports what's missing.

    Query Parameters:
        - platform (optional): Filter by platform (instagram, facebook, x, tiktok, linkedin, youtube)

    Returns:
        200: {
            "success": true,
            "data": {
                "profiles": list[dict],  # [{name, url, platform, entity_id, entity_name}, ...]
                "count": int,
                "platform": str,
                "scraping_issues": list[str]  # e.g. ["posts", "likes", "comments", "followers"]
            }
        }
        400: Invalid query parameters
        401: Missing or invalid API key
        500: Database error
    
    Example:
        GET /api/scraping/apify_profile_scraping?platform=instagram
        
        Response:
        {
            "success": true,
            "data": {
                "profiles": [
                    {
                        "name": "company_instagram",
                        "url": "https://instagram.com/company",
                        "platform": "instagram",
                        "entity_id": 1,
                        "entity_name": "Company Name"
                    }
                ],
                "count": 1,
                "platform": "instagram",
                "scraping_issues": ["comments", "likes"]
            }
        }
    """
    try:
        # Extract query parameters
        platform = request.args.get("platform")
        limit_raw = request.args.get("limit")
        
        limit = None
        if limit_raw is not None:
            try:
                limit = int(limit_raw)
                if limit <= 0:
                    raise ValueError()
            except ValueError:
                log_route_error(
                    ValueError(f"Invalid limit: {limit_raw}"),
                    SEVERITY_LOW,
                    400,
                    "Invalid query parameters"
                )
                return error_response("'limit' must be a positive integer", 400)
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Get failed profiles
        result = ScrapingService.get_failed_profiles_for_scraping(platform=platform, limit=limit)
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during failed profile fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during failed profile fetch")
        return server_error_response(500)


@scraping_bp.route("/posts", methods=["GET"])
@require_api_key
def fetch_posts():
    """
    Fetch posts for scraping with optional filters.
    Only returns posts that have not already been scraped today
    (i.e., posts with no comments inserted today).
    
    Query Parameters:
        - platform (optional): Filter by platform
        - start_date (optional): Filter posts created after this date (ISO 8601)
        - end_date (optional): Filter posts created before this date (ISO 8601)
    
    Returns:
        200: {
            "success": true,
            "data": {
                "session_id": str,
                "posts": list[dict],
                "count": int,
                "total_available": int
            }
        }
        400: Invalid query parameters
        401: Missing or invalid API key
        500: Database error
    """
    try:
        # Extract query parameters
        platform = request.args.get("platform")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        recorded_start_date = request.args.get("recorded_start_date") or request.args.get("recorded_start")
        recorded_end_date = request.args.get("recorded_end_date") or request.args.get("recorded_end")
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Fetch posts and create session
        result = ScrapingService.fetch_posts_for_scraping(
            platform=platform,
            start_date=start_date,
            end_date=end_date,
            recorded_start_date=recorded_start_date,
            recorded_end_date=recorded_end_date
        )
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during post fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during post fetch")
        return server_error_response(500)


@scraping_bp.route("/comments", methods=["POST"])
@require_api_key
def insert_comments():
    """
    Insert scraped comments in bulk.

    Request Body:
        {
            "session_id": str (optional),
            "comments": [
                {
                    "page_id": str,
                    "platform": str,
                    "post_id": str,
                    "id": str,
                    "text": str,
                    "username": str,
                    "timestamp": int (Unix timestamp),
                    "likes": int (optional),
                    "is_reply": bool (optional),
                    "parent_id": str (optional)
                }
            ],
            "post_results": [
                {
                    "page_id": str,
                    "platform": str,
                    "post_id": str
                }
            ] (optional — supply posts that were scraped but had 0 comments,
               so they are recorded as done rather than pending)
        }

    Returns:
        200: {
            "success": true,
            "data": {
                "session_id": str,
                "inserted": int,
                "skipped": int,
                "total": int
            }
        }
        400: Invalid request body or validation failure
        401: Missing or invalid API key
        500: Database error (transaction rolled back)
    """
    try:
        # Parse request body
        data = request.get_json()

        if not data:
            return error_response("Invalid request payload", 400)

        comments = data.get("comments", [])
        session_id = data.get("session_id")
        post_results = data.get("post_results")

        if not isinstance(comments, list):
            log_route_error(
                TypeError("Comments must be an array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("Comments must be an array", 400)

        if post_results is not None and not isinstance(post_results, list):
            log_route_error(
                TypeError("post_results must be an array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("post_results must be an array", 400)

        # Validate post_results entries if provided
        if post_results:
            for idx, pr in enumerate(post_results):
                for field in ("page_id", "platform", "post_id"):
                    if not pr.get(field):
                        return error_response(
                            f"post_results[{idx}] missing required field '{field}'", 400
                        )

        # Insert comments
        result = ScrapingService.insert_comment_batch(
            comments, session_id, post_results=post_results
        )

        # Add total count to response
        result["total"] = result["inserted"] + result["skipped"]

        return success_response(result, 200)
    
    except ValueError as e:
        # Rollback transaction on validation error
        db.session.rollback()
        
        log_route_error(e, SEVERITY_LOW, 400, "Validation failed")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        # Rollback transaction on database error
        db.session.rollback()
        
        # Update session status to failed if session_id provided
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        if session_id:
            try:
                ScrapingSessionRepository.update_status(
                    session_id, 
                    "failed", 
                    error_message=str(e)
                )
            except Exception:
                pass  # Best effort - don't fail if session update fails
        
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during comment insertion")
        return db_error_response(500)
    
    except Exception as e:
        # Rollback transaction on unexpected error
        db.session.rollback()
        
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during comment insertion")
        return server_error_response(500)


@scraping_bp.route("/own_scraper/profiles", methods=["GET"])
@require_api_key
def fetch_own_scraper_profiles():
    """
    Fetch accounts whose profile info is due for a refresh, with an
    optional platform filter, and create a scraping session. Mirrors
    /posts's envelope and behavior -- see api/docs/scraping_profiles.md.

    Deliberately NOT at plain /profiles: that path already exists upstream
    (ScrapingService.get_profiles_for_scraping, added independently) with a
    different response shape and no session tracking -- it's the data
    source for the Apify fallback pipeline, not this one. This route is
    namespaced under /own_scraper/ to avoid silently changing what /profiles
    returns for whatever already depends on it, since these two now solve
    genuinely different problems on the same resource rather than being
    interchangeable. See api/docs/scraping_profiles.md's note on this.

    Query Parameters:
        - platform (required): Only 'instagram' is supported today.
        - start_date, recorded_start_date, recorded_end_date (optional):
          accepted for client contract parity, not currently used to filter
          (see ScrapingService.fetch_profiles_for_scraping's docstring).

    Returns:
        200: {
            "success": true,
            "data": {
                "session_id": str,
                "profiles": list[{"account_id": str, "page_id": str, "url": str}],
                "count": int,
                "total_available": int
            }
        }
        400: Invalid/missing platform
        401: Missing or invalid API key
        500: Database error
    """
    try:
        platform = request.args.get("platform")
        start_date = request.args.get("start_date")
        recorded_start_date = request.args.get("recorded_start_date") or request.args.get("recorded_start")
        recorded_end_date = request.args.get("recorded_end_date") or request.args.get("recorded_end")

        result = ScrapingService.fetch_profiles_for_scraping(
            platform=platform,
            start_date=start_date,
            recorded_start_date=recorded_start_date,
            recorded_end_date=recorded_end_date,
        )

        return success_response(result, 200)

    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)

    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during profile fetch")
        return db_error_response(500)

    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during profile fetch")
        return server_error_response(500)


@scraping_bp.route("/profile-info", methods=["POST"])
@require_api_key
def insert_profile_info():
    """
    Insert scraped profile records in bulk.

    Request Body:
        {
            "session_id": str (optional),
            "profiles": [
                {
                    "page_id": str,
                    "platform": str,
                    "account_id": str,
                    ... every other field the scraper captured (followers,
                    biography, profile_image_link, posts, highlights, ...) ...
                }
            ],
            "profile_results": [
                {"page_id": str, "platform": str, "account_id": str}
            ] (optional -- every account actually visited this batch,
               scraped or not, so it isn't re-served on the next fetch)
        }

    Returns:
        200: {
            "success": true,
            "data": {"session_id": str, "inserted": int, "skipped": int, "total": int}
        }
        400: Invalid request body or validation failure
        401: Missing or invalid API key
        500: Database error (transaction rolled back)
    """
    try:
        data = request.get_json()

        if not data:
            return error_response("Invalid request payload", 400)

        profiles = data.get("profiles", [])
        session_id = data.get("session_id")
        profile_results = data.get("profile_results")

        if not isinstance(profiles, list):
            log_route_error(
                TypeError("profiles must be an array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("profiles must be an array", 400)

        if profile_results is not None and not isinstance(profile_results, list):
            log_route_error(
                TypeError("profile_results must be an array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("profile_results must be an array", 400)

        if profile_results:
            for idx, pr in enumerate(profile_results):
                for field in ("page_id", "platform", "account_id"):
                    if not pr.get(field):
                        return error_response(
                            f"profile_results[{idx}] missing required field '{field}'", 400
                        )

        result = ScrapingService.insert_profile_batch(
            profiles, session_id, profile_results=profile_results
        )

        return success_response(result, 200)

    except ValueError as e:
        db.session.rollback()
        log_route_error(e, SEVERITY_LOW, 400, "Validation failed")
        return error_response(str(e), 400)

    except SQLAlchemyError as e:
        db.session.rollback()

        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        if session_id:
            try:
                ScrapingSessionRepository.update_status(
                    session_id,
                    "failed",
                    error_message=str(e)
                )
            except Exception:
                pass  # Best effort -- don't fail if session update fails

        log_route_error(e, SEVERITY_HIGH, 500, "Database error during profile insertion")
        return db_error_response(500)

    except Exception as e:
        db.session.rollback()
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during profile insertion")
        return server_error_response(500)


@scraping_bp.route("/status/summary", methods=["GET"])
@require_auth("admin")
def get_scraping_summary():
    """
    Get aggregated scraping status summary for a specific date (admin only).
    
    Query Parameters:
        - date (optional): Date in ISO format (YYYY-MM-DD). Defaults to today.
        - platform (optional): Filter by platform (facebook, instagram, x, tiktok, linkedin, youtube)
    
    Returns:
        200: {
            "success": true,
            "data": {
                "date": str,
                "platform_filter": str | null,
                "total_sessions": int,
                "sessions_by_status": {"pending": int, "completed": int, "failed": int},
                "total_posts_fetched": int,
                "total_comments_inserted": int,
                "total_expected_comments": int,
                "comments_ratio": float | null,
                "duration_stats": {
                    "min_seconds": float,
                    "max_seconds": float,
                    "avg_seconds": float,
                    "min_formatted": str,
                    "max_formatted": str,
                    "avg_formatted": str
                } | null,
                "errors": [{"session_id": str, "error": str}]
            }
        }
        400: Invalid query parameters
        401: Missing or invalid token
        403: Insufficient permissions
        500: Database error
    """
    try:
        # Extract query parameters
        target_date = request.args.get("date")
        platform = request.args.get("platform")
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Validate date format if provided
        if target_date:
            try:
                from datetime import date
                date.fromisoformat(target_date)
            except ValueError:
                log_route_error(
                    ValueError(f"Invalid date format: {target_date}"),
                    SEVERITY_LOW,
                    400,
                    "Invalid query parameters"
                )
                return error_response("Invalid date format. Use ISO format (YYYY-MM-DD)", 400)
        
        # Get summary
        result = ScrapingService.get_daily_summary(
            target_date=target_date,
            platform=platform
        )
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during summary fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during summary fetch")
        return server_error_response(500)


@scraping_bp.route("/status/sessions", methods=["GET"])
@require_auth("admin")
def get_scraping_sessions():
    """
    Get all scraping sessions for a specific date (admin only).
    
    Query Parameters:
        - date (optional): Date in ISO format (YYYY-MM-DD). Defaults to today.
        - platform (optional): Filter by platform (facebook, instagram, x, tiktok, linkedin, youtube)
    
    Returns:
        200: {
            "success": true,
            "data": [
                {
                    "session_id": str,
                    "created_at": str,
                    "completed_at": str | null,
                    "posts_fetched": int,
                    "comments_inserted": int,
                    "status": str,
                    "error_message": str | null,
                    "duration_seconds": float (only for completed sessions)
                }
            ]
        }
        400: Invalid query parameters
        401: Missing or invalid token
        403: Insufficient permissions
        500: Database error
    """
    try:
        # Extract query parameters
        target_date = request.args.get("date")
        platform = request.args.get("platform")
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Validate date format if provided
        if target_date:
            try:
                from datetime import date
                date.fromisoformat(target_date)
            except ValueError:
                log_route_error(
                    ValueError(f"Invalid date format: {target_date}"),
                    SEVERITY_LOW,
                    400,
                    "Invalid query parameters"
                )
                return error_response("Invalid date format. Use ISO format (YYYY-MM-DD)", 400)
        
        # Get sessions
        result = ScrapingService.get_sessions_for_date(
            target_date=target_date,
            platform=platform
        )
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during sessions fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during sessions fetch")
        return server_error_response(500)


@scraping_bp.route("/sessions/<session_id>", methods=["GET"])
@require_api_key
def get_session_details(session_id):
    """
    Retrieve scraping session details.
    
    Path Parameters:
        - session_id: Session UUID
    
    Returns:
        200: {
            "success": true,
            "data": {
                "session_id": str,
                "created_at": str,
                "completed_at": str | None,
                "posts_fetched": int,
                "comments_inserted": int,
                "status": str,
                "error_message": str | None
            }
        }
        401: Missing or invalid API key
        404: Session not found
        500: Database error
    """
    try:
        # Fetch session details
        session_data = ScrapingService.get_session_details(session_id)
        
        if not session_data:
            log_route_error(
                ValueError(f"Session not found: {session_id}"),
                SEVERITY_MEDIUM,
                404,
                "Session not found"
            )
            return error_response(f"Scraping session not found: {session_id}", 404)
        
        return success_response(session_data, 200)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during session fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during session fetch")
        return server_error_response(500)


@scraping_bp.route("/sessions/<session_id>/complete", methods=["POST"])
@require_api_key
def complete_session(session_id):
    """
    Mark a scraping session as completed.
    Called by the external scraper when it has finished processing all posts
    for this session, regardless of whether comments were found.
    
    Path Parameters:
        - session_id: Session UUID
    
    Returns:
        200: {
            "success": true,
            "data": {
                "session_id": str,
                "status": "completed",
                "completed_at": str,
                "posts_fetched": int,
                "comments_inserted": int
            }
        }
        400: Session already completed or failed
        401: Missing or invalid API key
        404: Session not found
        500: Database error
    """
    try:
        result = ScrapingService.complete_scraping_session(session_id)
        
        if result is None:
            log_route_error(
                ValueError(f"Session not found: {session_id}"),
                SEVERITY_MEDIUM,
                404,
                "Session not found"
            )
            return error_response(f"Scraping session not found: {session_id}", 404)
        
        return success_response(result, 200)
    
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid session state")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        db.session.rollback()
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during session completion")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during session completion")
        return server_error_response(500)


@scraping_bp.route("/posts/today-status", methods=["GET"])
@require_auth("admin")
def get_today_posts_status():
    """
    Get the scraping status of posts scheduled for today (or a specific date).
    Returns lists of scraped and pending posts.
    
    Query Parameters:
        - date (optional): Date in ISO format (YYYY-MM-DD). Defaults to today.
        - platform (optional): Filter by platform (facebook, instagram, x, tiktok, linkedin, youtube)
        - start_date (optional): Filter posts created after this date (ISO 8601)
    
    Returns:
        200: {
            "success": true,
            "data": {
                "date": str,
                "platform_filter": str | null,
                "start_date_filter": str | null,
                "scraped_count": int,
                "pending_count": int,
                "total_count": int,
                "scraped_posts": list[dict],
                "pending_posts": list[dict]
            }
        }
        400: Invalid query parameters
        401: Missing or invalid API key
        500: Database error
    """
    try:
        # Extract query parameters
        target_date = request.args.get("date")
        platform = request.args.get("platform")
        start_date = request.args.get("start_date")
        recorded_start_date = request.args.get("recorded_start_date") or request.args.get("recorded_start")
        recorded_end_date = request.args.get("recorded_end_date") or request.args.get("recorded_end")
        
        # Validate platform if provided
        valid_platforms = ["facebook", "instagram", "x", "tiktok", "linkedin", "youtube"]
        if platform and platform not in valid_platforms:
            log_route_error(
                ValueError(f"Invalid platform: {platform}"),
                SEVERITY_LOW,
                400,
                "Invalid query parameters"
            )
            return error_response(f"Invalid platform. Must be one of: {', '.join(valid_platforms)}", 400)
        
        # Validate date format if provided
        if target_date:
            try:
                from datetime import date
                date.fromisoformat(target_date)
            except ValueError:
                log_route_error(
                    ValueError(f"Invalid date format: {target_date}"),
                    SEVERITY_LOW,
                    400,
                    "Invalid query parameters"
                )
                return error_response("Invalid date format. Use ISO format (YYYY-MM-DD)", 400)
        
        # Validate start_date format if provided
        if start_date:
            try:
                from datetime import datetime as dt
                dt.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                log_route_error(
                    ValueError(f"Invalid start_date format: {start_date}"),
                    SEVERITY_LOW,
                    400,
                    "Invalid query parameters"
                )
                return error_response("Invalid start_date format. Use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)", 400)
        
        # Fetch status
        result = ScrapingService.get_today_scraping_status(
            platform=platform,
            target_date=target_date,
            start_date=start_date,
            recorded_start_date=recorded_start_date,
            recorded_end_date=recorded_end_date
        )
        
        return success_response(result, 200)
        
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid query parameters")
        return error_response(str(e), 400)
    
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during today status fetch")
        return db_error_response(500)
    
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during today status fetch")
        return server_error_response(500)


# ---------------------------------------------------------------------------
# Scraper credentials -- session cookies for platforms that require a
# logged-in session (LinkedIn today). Managed from Brendex Admin via
# /api/admin/scraper-credentials (admin_routes.py, JWT-gated, values
# masked); these two are api-key-gated like the rest of this blueprint,
# for the VPS scraper itself to fetch the real value and report back
# whether it still works. See api/models/scraper_credential_model.py.
# ---------------------------------------------------------------------------

@scraping_bp.route("/credentials/<platform>", methods=["GET"])
@require_api_key
def get_scraper_credential(platform):
    """
    The raw stored credential for `platform` (currently: the cookie jar).
    Not exposed anywhere admin-facing -- see ScraperCredentialService.

    Query Parameters:
        - credential_type (optional, default 'cookies')

    Returns:
        200: {"success": true, "data": {"platform": str, "credential_type": str, "value": ...}}
        400: Unsupported platform/credential_type, or nothing stored yet
        401: Missing or invalid API key
    """
    try:
        credential_type = request.args.get("credential_type", "cookies")
        value = ScraperCredentialService.get_raw_for_scraper(platform, credential_type)
        return success_response({"platform": platform, "credential_type": credential_type, "value": value})
    except ScraperCredentialError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid scraper credential request")
        return error_response(str(e), 400)
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error fetching scraper credential")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error fetching scraper credential")
        return server_error_response(500)


@scraping_bp.route("/credentials/<platform>/report-check", methods=["POST"])
@require_api_key
def report_scraper_credential_check(platform):
    """
    Record the outcome of the scraper's own real run against `platform`,
    the active freshness signal shown in Brendex Admin. Call this once per
    run that actually used the credential, not as a separate synthetic
    health check.

    Body: {"status": "ok"|"auth_failed"|"error", "detail": str (optional),
           "credential_type": str (optional, default "cookies")}

    Returns:
        200: {"success": true, "data": {...masked credential row...}}
        400: Missing/invalid status, or nothing stored yet for this platform
        401: Missing or invalid API key
    """
    try:
        payload = request.get_json() or {}
        status = payload.get("status")
        if not status:
            return error_response("Missing required field: 'status'.", 400)

        result = ScraperCredentialService.report_check(
            platform=platform,
            status=status,
            detail=payload.get("detail"),
            credential_type=payload.get("credential_type", "cookies"),
        )
        return success_response(result)
    except ScraperCredentialError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid scraper credential check report")
        return error_response(str(e), 400)
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error reporting scraper credential check")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error reporting scraper credential check")
        return server_error_response(500)


# ---------------------------------------------------------------------------
# Manual scrape triggers -- queued from Brendex Admin via
# /api/admin/scraping/trigger (admin_routes.py, JWT-gated). These two are
# api-key-gated like the rest of this blueprint, for the VPS-side poller
# (trigger_watcher.py) to claim the oldest pending request and report back
# what happened when it ran. See api/models/scrape_trigger_request_model.py.
# ---------------------------------------------------------------------------

@scraping_bp.route("/trigger-requests/next", methods=["GET"])
@require_api_key
def claim_next_trigger_request():
    """
    Atomically claim the oldest pending manual-trigger request, if any.
    Meant to be polled every ~30s by the VPS watcher.

    Returns:
        200: {"success": true, "data": {"trigger": {...} | null}}
        401: Missing or invalid API key
    """
    try:
        result = ScrapeTriggerService.claim_next_pending()
        return success_response({"trigger": result})
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error claiming trigger request")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error claiming trigger request")
        return server_error_response(500)


@scraping_bp.route("/trigger-requests/<int:request_id>/report", methods=["POST"])
@require_api_key
def report_trigger_result(request_id):
    """
    Record the outcome of a manually-triggered scrape run.

    Body: {"status": "done"|"failed", "detail": str (optional)}

    Returns:
        200: {"success": true, "data": {...trigger row...}}
        400: Missing/invalid status, or no such request id
        401: Missing or invalid API key
    """
    try:
        payload = request.get_json() or {}
        status = payload.get("status")
        if not status:
            return error_response("Missing required field: 'status'.", 400)

        result = ScrapeTriggerService.report_result(
            request_id=request_id,
            status=status,
            detail=payload.get("detail"),
        )
        return success_response(result)
    except ScrapeTriggerError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid trigger-request report")
        return error_response(str(e), 400)
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error reporting trigger result")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error reporting trigger result")
        return server_error_response(500)

