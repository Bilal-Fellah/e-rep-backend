from flask import Blueprint, jsonify, request

from api.services.ai_insight_service import SERIALIZERS, get_or_generate_insight


bp = Blueprint("ai_insight", __name__)


@bp.route("/api/insights", methods=["POST"])
def get_insight():
    payload = request.get_json(silent=True) or {}

    view_type = payload.get("view_type")
    filters = payload.get("filters") or {}
    data = payload.get("data")

    if view_type not in SERIALIZERS:
        return jsonify({"error": "invalid_view_type"}), 400

    result = get_or_generate_insight(view_type, filters, data)

    if "error" in result:
        return jsonify(result), 502

    return jsonify(result), 200
