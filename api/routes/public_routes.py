# routes/public_routes.py
from flask import Blueprint, request
from api.repositories.page_history_repository import PageHistoryRepository
from api.routes.main import error_response, success_response, register_blueprint_error_handlers

public_bp = Blueprint("public", __name__)

register_blueprint_error_handlers(public_bp)

ALLOWED_ENTITY_TYPES = ("company", "influencer", "small-business")


@public_bp.route("/ranking", methods=["GET"])
def public_ranking():
    try:
        # Optional `?type=` narrows the public preview to a single entity kind
        # (e.g. influencers for the Brendex creator teaser).
        entity_type = request.args.get("type")
        if entity_type:
            entity_type = entity_type.strip().lower()
            if entity_type not in ALLOWED_ENTITY_TYPES:
                return error_response(
                    f"type must be one of {list(ALLOWED_ENTITY_TYPES)}", 400
                )

        data = PageHistoryRepository.get_public_ranking()

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No ranking data available", 404)

        if entity_type:
            data = [
                row
                for row in data
                if str(row.get("type") or "").lower() == entity_type
            ]
            if not data:
                return error_response("No ranking data available", 404)

        # Top 10 for the requested scope
        top_global = data[:10]

        result = {
            "top_global": top_global,
        }

        return success_response(result, 200)

    except ValueError:
        return error_response("Invalid request data", 400)