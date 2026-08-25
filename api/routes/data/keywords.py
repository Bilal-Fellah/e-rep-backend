# Route handlers for the client-owned TikTok keyword watchlist (tracked
# keywords + the mentions found for them). See api/docs/keyword_mentions.md.
from flask import request

from . import data_bp
from api.routes.main import success_response, error_response
from api.services.tracked_keyword_service import TrackedKeywordError, TrackedKeywordService
from api.utils.permissions import require_role
# Import new models so Alembic/Flask-Migrate picks them up for migrations
from api.models.tracked_keyword_model import TrackedKeyword  # noqa: F401
from api.models.keyword_mention_model import KeywordMention  # noqa: F401


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
