# routes/public_routes.py
from flask import Blueprint
from api.repositories.page_history_repository import PageHistoryRepository
from api.routes.main import error_response, success_response, register_blueprint_error_handlers

public_bp = Blueprint("public", __name__)

register_blueprint_error_handlers(public_bp)


@public_bp.route("/ranking", methods=["GET"])
def public_ranking():
    try:
        data = PageHistoryRepository.get_public_ranking()

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No ranking data available", 404)

        # Top 10 global
        top_global = data[:10]

        result = {
            "top_global": top_global,
        }

        return success_response(result, 200)

    except ValueError:
        return error_response("Invalid request data", 400)