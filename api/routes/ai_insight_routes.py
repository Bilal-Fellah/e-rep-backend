from flask import Blueprint, jsonify, request

from api.routes.main import SEVERITY_HIGH, SEVERITY_LOW, log_route_error
from api.services.ai_insight_service import SERIALIZERS, get_or_generate_insight


bp = Blueprint("ai_insight", __name__)


@bp.route("/api/insights", methods=["POST"])
def get_insight():
    try:
        payload = request.get_json(silent=True) or {}

        view_type = payload.get("view_type")
        filters = payload.get("filters") or {}
        data = payload.get("data")

        if view_type not in SERIALIZERS:
            err = ValueError(f"invalid view_type: {view_type}")
            log_route_error(err, SEVERITY_LOW, 400, "Invalid request data")
            return jsonify({"error": "invalid_view_type"}), 400

        result = get_or_generate_insight(view_type, filters, data)

        if "error" in result:
            return jsonify(result), 502

        return jsonify(result), 200

    except ValueError as error:
        log_route_error(error, SEVERITY_LOW, 400, "Invalid request data")
        return jsonify({"error": "invalid_request"}), 400
    except Exception as error:
        log_route_error(error, SEVERITY_HIGH, 500, "Unexpected error in insights route")
        return jsonify({"error": "server_error"}), 500
