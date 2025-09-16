import os
from flask import request
import jwt
from api.routes.main import error_response, success_response
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from . import data_bp

SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_category", methods=["POST"])
def add_category():
    allowed_roles = ['admin']

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        if not payload:
            return error_response("No valid token has been sent", 401)
        
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403 )

        data = request.get_json()
        name = data.get("name", "").strip().lower()
        parent_id = data.get("parent_id")

        if not name:
            return error_response("Missing required field: 'name'.", 400)

        category = CategoryRepository.create(name=name, parent_id=parent_id)
        return success_response({
            "id": category.id,
            "name": category.name,
            "parent_id": category.parent_id
        }, 201)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)
    

@data_bp.route("/delete_category", methods=["POST"])
def delete_category():
    allowed_roles = ['admin']
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        if not payload:
            return error_response("No valid token has been sent", 401)
        
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403 )

        category_id = request.json.get("id")
        if not category_id:
            return error_response("Missing required field: 'id'.", 400)

        deleted = CategoryRepository.delete(category_id)
        if not deleted:
            return error_response(f"No category found with id {category_id}", 404)

        return success_response({"deleted_id": category_id}, 200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_all_categories", methods=["GET"])
def get_all_categories():
    allowed_roles = ['admin', 'registered', 'subscribed']
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        if not payload:
            return error_response("No valid token has been sent", 401)
        
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403 )

        categories = CategoryRepository.get_all()
        if not categories:
            return error_response("No categories found.", 404)

        data = [
            {"id": c.id, "name": c.name, "parent_id": c.parent_id}
            for c in categories
        ]
        return success_response(data, 200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


