# routes/public_routes.py
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

        return success_response(data, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", 500)