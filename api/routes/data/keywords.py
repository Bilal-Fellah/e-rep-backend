# Route handlers for the client-owned TikTok keyword watchlist (tracked
# keywords + the mentions found for them). See api/docs/keyword_mentions.md.
from flask import request

from . import data_bp
from api.routes.main import success_response, error_response
from api.services.tracked_keyword_service import TrackedKeywordError, TrackedKeywordService
from api.services.scrape_trigger_service import ScrapeTriggerError, ScrapeTriggerService
from api.utils.permissions import require_role
# Import new models so Alembic/Flask-Migrate picks them up for migrations
from api.models.tracked_keyword_model import TrackedKeyword  # noqa: F401
from api.models.keyword_mention_model import KeywordMention  # noqa: F401

# Only mode this feature has -- fixed rather than accepted from the request
# body, since Erup's "Run now" button is deliberately narrow (this route,
# not Brendex Admin's generic platform/mode trigger panel).
SEARCH_NOW_PLATFORM = "tiktok"
SEARCH_NOW_MODE = "keyword-search"


@data_bp.route("/keywords", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def list_keywords():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    return success_response(TrackedKeywordService.list_for_user(user_id), 200)


@data_bp.route("/keywords", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def create_keyword():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    payload = request.get_json(silent=True) or {}
    try:
        return success_response(TrackedKeywordService.create(user_id, payload), 201)
    except TrackedKeywordError as e:
        return error_response(str(e), 400)


@data_bp.route("/keywords/<int:keyword_id>", methods=["DELETE"])
@require_role("admin", "registered", "subscribed")
def delete_keyword(keyword_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    deleted = TrackedKeywordService.delete(user_id, keyword_id)
    if not deleted:
        return error_response("Keyword not found", 404)
    return success_response({"deleted": True}, 200)


@data_bp.route("/keywords/<int:keyword_id>/mentions", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def list_keyword_mentions(keyword_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)

    mentions = TrackedKeywordService.list_mentions(user_id, keyword_id, limit=limit, offset=offset)
    if mentions is None:
        return error_response("Keyword not found", 404)
    return success_response(mentions, 200)


@data_bp.route("/keywords/search-now", methods=["GET"])
@require_role("admin")
def get_keyword_search_now_status():
    """Latest manual keyword-search run, if any -- backs the "Run now"
    button's status display on Erup's Keywords page."""
    return success_response(
        ScrapeTriggerService.latest_for(SEARCH_NOW_PLATFORM, SEARCH_NOW_MODE), 200
    )


@data_bp.route("/keywords/search-now", methods=["POST"])
@require_role("admin")
def trigger_keyword_search_now():
    """Admin-only: queue an immediate TikTok keyword-search pass instead of
    waiting for tomorrow's scheduled timer. Same queue Brendex Admin's
    generic trigger panel uses -- the VPS watcher picks it up within ~30s."""
    user_id = getattr(request, "user_id", None)
    try:
        result = ScrapeTriggerService.request_trigger(
            platform=SEARCH_NOW_PLATFORM, mode=SEARCH_NOW_MODE, requested_by=user_id
        )
    except ScrapeTriggerError as e:
        return error_response(str(e), 400)
    return success_response(result, 201)
