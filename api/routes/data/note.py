from collections import defaultdict
from datetime import datetime, timezone, timedelta
import math
import os
from api.repositories.note_repository import NoteRepository
from api.repositories.page_repository import PageRepository
from api.repositories.user_repository import UserRepository
from api.utils.data_keys import platform_metrics
import jwt
from api.repositories.page_history_repository import PageHistoryRepository
from flask import Blueprint, request, jsonify
from api.routes.main import error_response, success_response
from api.repositories.entity_repository import EntityRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from sqlalchemy.exc import SQLAlchemyError


notes_bp = Blueprint("notes", __name__)

@notes_bp.route("/create_note", methods=["POST"])
def create_note():
    data = request.get_json() or {}

    # ---- Validation ----
    required_fields = ["content", "target_type", "target_id", "user_id"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    user_id = int(data["user_id"])

    if not UserRepository.get_by_id(user_id):
        return jsonify({"error": "User doesn't exist, can't create note"}), 404

    note = NoteRepository.create(
        author_id=user_id,
        title=data.get("title"),
        content=data["content"],
        target_type=data["target_type"], # post or graph
        target_id=data["target_id"], # if post, then post.id if graph, then entity.id
        context_data=data.get("context_data"),
        visibility=data.get("visibility", "private"),
    )

    return success_response(data=note, status_code=201)



@notes_bp.route("/get_notes_for_target", methods=["GET"])
def get_notes_for_target():
    """ Get notes about a specific post, or a specific entity (graph) """

    target_type = request.args.get("target_type")
    target_id = request.args.get("target_id", type=int)
    user_id = request.args.get("user_id", type=int)

    if not target_type or not target_id:
        return jsonify({"error": "target_type and target_id are required"}), 400

    notes = NoteRepository.get_for_target(
        target_type=target_type,
        target_id=target_id,
        user_id=user_id
    )

    data = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "context_data": n.context_data,
            "visibility": n.visibility,
            "status": n.status,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat()
        }
        for n in notes
    ]
    return success_response(data=data, status_code=200)
