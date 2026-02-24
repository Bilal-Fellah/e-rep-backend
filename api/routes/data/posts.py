from flask import request
from . import data_bp
from api.repositories.post_repository import PostRepository
from api.routes.main import success_response, error_response


@data_bp.route("/get_post", methods=["GET"])
def get_post():
    """Get a single post by its composite key: page_id + platform + post_id."""
    page_id  = request.args.get("page_id")
    platform = request.args.get("platform")
    post_id  = request.args.get("post_id")

    if not page_id or not platform or not post_id:
        return error_response("page_id, platform, and post_id are required", 400)

    post = PostRepository.get_by_composite_key(page_id, platform, post_id)
    if not post:
        return error_response("Post not found", 404)

    return success_response(data=post.to_dict())


@data_bp.route("/get_posts_by_platform", methods=["GET"])
def get_posts_by_platform():
    """Get all latest posts for a given platform."""
    platform = request.args.get("platform")
    if not platform:
        return error_response("platform is required", 400)

    posts = PostRepository.get_by_platform(platform)
    if not posts:
        return error_response("No posts found", 404)

    return success_response(data=[p.to_dict() for p in posts])


@data_bp.route("/get_posts_by_page", methods=["GET"])
def get_posts_by_page():
    """Get all latest posts for a page, optionally filtered by platform."""
    page_id  = request.args.get("page_id")
    platform = request.args.get("platform")  # optional

    if not page_id:
        return error_response("page_id is required", 400)

    posts = PostRepository.get_by_page(page_id, platform)
    if not posts:
        return error_response("No posts found", 404)

    return success_response(data=[p.to_dict() for p in posts])


@data_bp.route("/get_posts_by_entity", methods=["GET"])
def get_posts_by_entity():
    """Get all latest posts across every page belonging to an entity."""
    entity_id = request.args.get("entity_id", type=int)
    platform  = request.args.get("platform")  # optional filter

    if not entity_id:
        return error_response("entity_id is required", 400)

    posts = PostRepository.get_by_entity(entity_id, platform)
    if not posts:
        return error_response("No posts found", 404)

    return success_response(data=[p.to_dict() for p in posts])


@data_bp.route("/get_post_history", methods=["GET"])
def get_post_history():
    """Get the full snapshot history of a single post from posts_history_mv."""
    page_id  = request.args.get("page_id")
    platform = request.args.get("platform")
    post_id  = request.args.get("post_id")

    if not page_id or not platform or not post_id:
        return error_response("page_id, platform, and post_id are required", 400)

    history = PostRepository.get_post_history(page_id, platform, post_id)
    if not history:
        return error_response("No history found for this post", 404)

    return success_response(data=[h.to_dict() for h in history])