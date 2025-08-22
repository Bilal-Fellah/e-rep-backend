from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.route("/check")
def check_health():
    return jsonify(status="ok"), 200
