from api.models.entity_model import Entity
from api.repositories.entity_repository import EntityRepository
from api.repositories.note_repository import NoteRepository
from api.repositories.post_repository import PostRepository
from api.repositories.user_repository import UserRepository
from flask import Blueprint, request, jsonify
from api.routes.main import error_response, success_response
from . import data_bp


def _note_dict(n):
    return {
        "id": n.id,
        "author_id": n.author_id,
        "title": n.title,
        "content": n.content,
        "target_type": n.target_type,
        "target_id": n.target_id,
        "context_data": n.context_data,
        "visibility": n.visibility,
        "status": n.status,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }


@data_bp.route("/create_note", methods=["POST"])
def create_note():
    data = request.get_json() or {}

    required_fields = ["content", "target_type", "target_id", "user_id"]
    for field in required_fields:
        if field not in data:
            return error_response(f"{field} is required", 400)

    user_id = int(data["user_id"])

    if data["target_type"] not in ["post", "interactions_graph", "followers_graph"]:
        return error_response("Invalid target_type, must be 'post', 'interactions_graph', or 'followers_graph'", 400)
    
    if data['target_type'] == 'post' and not PostRepository.get_by_id(data["target_id"]):
        return error_response("Target post not found", 404)
    
    elif data["target_type"] in ["interactions_graph", "followers_graph"] and not EntityRepository.get_by_id(data["target_id"]):
        return error_response("Target entity not found", 404)
    
    if not UserRepository.get_by_id(user_id):
        return error_response("User doesn't exist, can't create note", 404)
    
    note = NoteRepository.create(
        author_id=user_id,
        title=data.get("title"),
        content=data["content"],
        target_type=data["target_type"],   # "post" | "interactions_graph"
        target_id=data["target_id"],       # post.id or entity.id
        context_data=data.get("context_data"),
        visibility=data.get("visibility", "private"),
    )
    return success_response(data=_note_dict(note), status_code=201)


@data_bp.route("/get_note/<int:note_id>", methods=["GET"])
def get_note(note_id):
    """Get a single note by its ID."""
    user_id = request.args.get("user_id", type=int)

    note = NoteRepository.get_by_id(note_id)
    if not note:
        return error_response("Note not found", 404)

    if not NoteRepository.can_view(note, user_id):
        return error_response("Access denied", 403)

    return success_response(data=_note_dict(note), status_code=200)


@data_bp.route("/get_notes_for_target", methods=["GET"])
def get_notes_for_target():
    """Get notes about a specific post or entity (graph)."""
    target_type = request.args.get("target_type")
    target_id = request.args.get("target_id", type=int)
    user_id = request.args.get("user_id", type=int)
    include_archived = request.args.get("include_archived", "false").lower() == "true"

    if not target_type or not target_id:
        return error_response("target_type and target_id are required", 400)

    notes = NoteRepository.get_for_target(
        target_type=target_type,
        target_id=target_id,
        user_id=user_id,
        include_archived=include_archived,
    )
    return success_response(data=[_note_dict(n) for n in notes], status_code=200)


@data_bp.route("/get_notes_by_author", methods=["GET"])
def get_notes_by_author():
    """Get all notes written by a specific user."""
    author_id = request.args.get("author_id", type=int)
    include_archived = request.args.get("include_archived", "false").lower() == "true"

    if not author_id:
        return error_response("author_id is required", 400)

    notes = NoteRepository.get_by_author(
        author_id=author_id,
        include_archived=include_archived,
    )
    return success_response(data=[_note_dict(n) for n in notes], status_code=200)


@data_bp.route("/update_note/<int:note_id>", methods=["POST"])
def update_note(note_id):
    """Update title, content, context_data, or visibility of a note."""
    data = request.get_json() or {}
    user_id = data.get("user_id")

    if not user_id:
        return error_response("user_id is required", 400)

    note = NoteRepository.get_by_id(note_id)
    if not note:
        return error_response("Note not found", 404)

    if not NoteRepository.can_edit(note, user_id):
        return error_response("Access denied — you are not the author", 403)

    updated = NoteRepository.update(
        note,
        title=data.get("title"),
        content=data.get("content"),
        context_data=data.get("context_data"),
        visibility=data.get("visibility"),
    )
    return success_response(data=_note_dict(updated), status_code=200)


@data_bp.route("/archive_note/<int:note_id>", methods=["POST"])
def archive_note(note_id):
    """Set a note's status to 'archived'."""
    data = request.get_json() or {}
    user_id = data.get("user_id")

    if not user_id:
        return error_response("user_id is required", 400)

    note = NoteRepository.get_by_id(note_id)
    if not note:
        return error_response("Note not found", 404)

    if not NoteRepository.can_edit(note, user_id):
        return error_response("Access denied — you are not the author", 403)

    NoteRepository.update(note, status="archived")
    return success_response(data={"message": "Note archived"}, status_code=200)


@data_bp.route("/delete_note/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    """Soft-delete a note (sets status to 'deleted')."""
    data = request.get_json() or {}
    user_id = data.get("user_id")

    if not user_id:
        return error_response("user_id is required", 400)

    note = NoteRepository.get_by_id(note_id)
    if not note:
        return error_response("Note not found", 404)

    if not NoteRepository.can_edit(note, user_id):
        return error_response("Access denied — you are not the author", 403)

    NoteRepository.soft_delete(note)
    return success_response(data={"message": "Note deleted"}, status_code=200)
