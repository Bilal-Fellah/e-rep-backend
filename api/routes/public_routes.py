# routes/public_routes.py
from collections import defaultdict
from flask import Blueprint
from api.repositories.page_history_repository import PageHistoryRepository
from api.routes.main import error_response, success_response

public_bp = Blueprint("public", __name__)


@public_bp.route("/ranking", methods=["GET"])
def public_ranking():
    try:
        data = PageHistoryRepository.get_public_ranking()

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No ranking data available", 404)

        # Top 10 global
        top_global = data[:10]
        top_global_ids = {e["entity_id"] for e in top_global}

        # Top 1 per root category (skip if already in top 10)
        top_by_category = {}
        for entity in data:
            cat = entity.get("category")
            if cat and cat not in top_by_category:
                top_by_category[cat] = entity

        category_extras = [
            e for e in top_by_category.values()
            if e["entity_id"] not in top_global_ids
        ]

        result = {
            "top_global": top_global,
            "top_by_category": category_extras,
        }

        return success_response(result, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", 500)