from flask import Blueprint, jsonify

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    return jsonify({"message": "API is running"})
