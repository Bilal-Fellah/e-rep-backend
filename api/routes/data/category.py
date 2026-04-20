# Data API endpoints for category.
import os
from flask import request
from api.routes.main import error_response, success_response
from api.repositories.category_repository import CategoryRepository
from . import data_bp

SECRET = os.environ.get("SECRET_KEY")


def _serialize_category(category):
    return {
        "id": category.id,
        "name": category.name,
        "name_french": category.name_french,
        "parent_id": category.parent_id,
        "is_active": category.is_active,
    }

@data_bp.route("/add_category", methods=["POST"])
def add_category():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403 )

        data = request.get_json()
        name = data.get("name", "").strip().lower()
        name_french = data.get("name_french")
        if isinstance(name_french, str):
            name_french = name_french.strip().lower() or None
        parent_id = data.get("parent_id")

        if not name:
            return error_response("Missing required field: 'name'.", 400)

        category = CategoryRepository.create(name=name, name_french=name_french, parent_id=parent_id)
        return success_response(_serialize_category(category), 201)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
    

@data_bp.route("/delete_category", methods=["POST"])
def delete_category():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403 )

        category_id = request.json.get("id")
        if not category_id:
            return error_response("Missing required field: 'id'.", 400)

        deleted = CategoryRepository.delete(category_id)
        if not deleted:
            return error_response(f"No category found with id {category_id}", 404)

        return success_response({"deleted_id": category_id}, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_all_categories", methods=["GET"])
def get_all_categories():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403 )

        categories = CategoryRepository.get_all()
        if not categories:
            return error_response("No categories found.", 404)

        data = [_serialize_category(category) for category in categories]
        return success_response(data, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/get_active_categories", methods=["GET"])
def get_active_categories():
    try:
        categories = CategoryRepository.get_all_active()
        if not categories:
            return error_response("No active categories found.", 404)

        data = [_serialize_category(category) for category in categories]
        return success_response(data, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


