# Data API endpoints for comments.
from flask import request
from . import data_bp
from api.repositories.comment_repository import CommentRepository
from api.routes.main import success_response, error_response


@data_bp.route("/get_comments_by_post", methods=["GET"])
def get_comments_by_post():
    """Get all comments for a specific post."""
    page_id = request.args.get("page_id")
    platform = request.args.get("platform")
    post_id = request.args.get("post_id")

    if not page_id or not platform or not post_id:
        return error_response("page_id, platform, and post_id are required", 400)

    comments = CommentRepository.get_by_post(page_id, platform, post_id)
    if not comments:
        return error_response("No comments found for this post", 404)

    return success_response(data=[c.to_dict() for c in comments])


@data_bp.route("/get_unprocessed_comments", methods=["GET"])
def get_unprocessed_comments():
    """Get comments that have not been processed for labeling."""
    limit = request.args.get("limit", type=int)

    comments = CommentRepository.get_unprocessed(limit)
    if not comments:
        return error_response("No unprocessed comments found", 404)

    return success_response(data=[c.to_dict() for c in comments])


@data_bp.route("/get_comments_by_label", methods=["GET"])
def get_comments_by_label():
    """Get all comments with a specific label."""
    label = request.args.get("label", type=int)

    if label is None:
        return error_response("label is required", 400)

    if label not in range(5):
        return error_response("label must be between 0 and 4", 400)

    comments = CommentRepository.get_by_label(label)
    if not comments:
        return error_response("No comments found with this label", 404)

    return success_response(data=[c.to_dict() for c in comments])


@data_bp.route("/update_comment_label", methods=["POST"])
def update_comment_label():
    """Update the label and confidence for a single comment."""
    data = request.get_json()

    if not data:
        return error_response("Request body is required", 400)

    comment_id = data.get("comment_id")
    label = data.get("label")
    confidence = data.get("confidence")

    if comment_id is None:
        return error_response("comment_id is required", 400)

    if label is None:
        return error_response("label is required", 400)

    if label not in range(5):
        return error_response("label must be between 0 and 4", 400)

    if confidence is not None and not (0.0 <= confidence <= 1.0):
        return error_response("confidence must be between 0.0 and 1.0", 400)

    try:
        comment = CommentRepository.update_label(comment_id, label, confidence)
        if not comment:
            return error_response("Comment not found", 404)

        return success_response(data=comment.to_dict())
    except ValueError as e:
        return error_response(str(e), 400)


@data_bp.route("/bulk_update_comment_labels", methods=["POST"])
def bulk_update_comment_labels():
    """Bulk update labels and confidence scores for multiple comments."""
    data = request.get_json()

    if not data:
        return error_response("Request body is required", 400)

    label_updates = data.get("label_updates")

    if not label_updates or not isinstance(label_updates, list):
        return error_response("label_updates (list) is required", 400)

    # Validate each update
    for i, update in enumerate(label_updates):
        if not isinstance(update, dict):
            return error_response(f"Invalid update at index {i}: must be an object", 400)

        comment_id = update.get("comment_id")
        label = update.get("label")
        confidence = update.get("confidence")

        if comment_id is None:
            return error_response(f"comment_id is required at index {i}", 400)

        if label is None:
            return error_response(f"label is required at index {i}", 400)

        if label not in range(5):
            return error_response(f"label must be between 0 and 4 at index {i}", 400)

        if confidence is not None and not (0.0 <= confidence <= 1.0):
            return error_response(f"confidence must be between 0.0 and 1.0 at index {i}", 400)

    try:
        updated_count = CommentRepository.bulk_update_labels(label_updates)
        return success_response(data={"updated_count": updated_count})
    except ValueError as e:
        return error_response(str(e), 400)


@data_bp.route("/mark_comments_processed", methods=["POST"])
def mark_comments_processed():
    """Mark multiple comments as processed."""
    data = request.get_json()

    if not data:
        return error_response("Request body is required", 400)

    comment_ids = data.get("comment_ids")

    if not comment_ids or not isinstance(comment_ids, list):
        return error_response("comment_ids (list) is required", 400)

    if not all(isinstance(cid, int) for cid in comment_ids):
        return error_response("All comment_ids must be integers", 400)

    updated_count = CommentRepository.bulk_mark_processed(comment_ids)
    return success_response(data={"updated_count": updated_count})


@data_bp.route("/comment_processing_stats", methods=["GET"])
def comment_processing_stats():
    """Get statistics about comment processing status."""
    from api.models.comment_model import Comment, db

    total_count = db.session.query(Comment).count()
    processed_count = CommentRepository.count_by_processing_status(True)
    unprocessed_count = CommentRepository.count_by_processing_status(False)

    # Count by label
    label_counts = {}
    for label in range(5):
        from sqlalchemy import func
        count = db.session.query(func.count(Comment.id)).filter(Comment.label == label).scalar()
        label_counts[label] = count or 0

    # Count unlabeled (label is NULL)
    unlabeled_count = db.session.query(func.count(Comment.id)).filter(Comment.label.is_(None)).scalar() or 0

    return success_response(data={
        "total": total_count,
        "processed": processed_count,
        "unprocessed": unprocessed_count,
        "labeled": {f"label_{label}": count for label, count in label_counts.items()},
        "unlabeled": unlabeled_count
    })
