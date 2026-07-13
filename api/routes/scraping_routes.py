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
from api.repositories.scraping_session_repository import ScrapingSessionRepository
from api.utils.api_key_auth import require_api_key
from api.utils.permissions import require_auth
from api.models.comment_model import db


scraping_bp = Blueprint("scraping", __name__, url_prefix="/api/scraping")
register_blueprint_error_handlers(scraping_bp)


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
            end_date=end_date
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
            ]
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
        
        if not comments:
            log_route_error(
                ValueError("Empty comments array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("Comments array is required and cannot be empty", 400)
        
        if not isinstance(comments, list):
            log_route_error(
                TypeError("Comments must be an array"),
                SEVERITY_LOW,
                400,
                "Invalid request data"
            )
            return error_response("Comments must be an array", 400)
        
        # Insert comments
        result = ScrapingService.insert_comment_batch(comments, session_id)
        
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


@scraping_bp.route("/posts/today-status", methods=["GET"])
@require_auth("admin")
def get_today_posts_status():
    """
    Get the scraping status of posts scheduled for today (or a specific date).
    Returns lists of scraped and pending posts.
    
    Query Parameters:
        - date (optional): Date in ISO format (YYYY-MM-DD). Defaults to today.
        - platform (optional): Filter by platform (facebook, instagram, x, tiktok, linkedin, youtube)
    
    Returns:
        200: {
            "success": true,
            "data": {
                "date": str,
                "platform_filter": str | null,
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
        
        # Fetch status
        result = ScrapingService.get_today_scraping_status(
            platform=platform,
            target_date=target_date
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

