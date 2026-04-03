from flask import Blueprint, jsonify
from api.routes.main import register_blueprint_error_handlers

health_bp = Blueprint("health", __name__)

register_blueprint_error_handlers(health_bp)

@health_bp.route("/check")
def check_health():
    return jsonify(status="ok"), 200
