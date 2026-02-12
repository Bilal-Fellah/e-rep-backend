

from sys import platform
from flask import Blueprint, request, jsonify
from . import data_bp
from api.repositories.post_repository import PostRepository
from api.routes.main import success_response


# posts_bp = Blueprint("posts", __name__)

@data_bp.route("/get_post_by_id", methods=["GET"])
def get_post_by_id():
    post_id = int(request.args.get("id"))

    post = PostRepository.get_by_id(post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 400
    data = post.to_dict()
    
    return success_response(data=data)
@data_bp.route("/get_post_by_platform", methods=["GET"])
def get_post_by_platform():
    platform = request.args.get("platform")

    if not platform:
        return jsonify({"error": "platform is required"}), 400

    posts = PostRepository.get_post_by_platform(
        platform=platform,
    )
    if not posts:
        return jsonify({"error": "Post not found"}), 404
    data = [r.to_dict() for r in posts] 
    return success_response(data=data)