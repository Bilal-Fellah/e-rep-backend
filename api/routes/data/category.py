from flask import request
from api.routes.main import error_response, success_response
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from . import data_bp


@data_bp.route("/add_category", methods=["POST"])
def add_category():
    try:
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

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/delete_category", methods=["POST"])
def delete_category():
    try:
        category_id = request.json.get("id")
        if not category_id:
            return error_response("Missing required field: 'id'.", 400)

        deleted = CategoryRepository.delete(category_id)
        if not deleted:
            return error_response(f"No category found with id {category_id}", 404)

        return success_response({"deleted_id": category_id}, 200)

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_all_categories", methods=["GET"])
def get_all_categories():
    try:
        categories = CategoryRepository.get_all()
        if not categories:
            return error_response("No categories found.", 404)

        data = [
            {"id": c.id, "name": c.name, "parent_id": c.parent_id}
            for c in categories
        ]
        return success_response(data, 200)

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/toa", methods=["GET"])
def toa():
    try:
        entity_categories = EntityCategoryRepository.get_all()
        if not entity_categories:
            return error_response("No entity-category mappings found.", 404)

        data = [
            {"entity_id": ec.entity_id, "category_id": ec.category_id}
            for ec in entity_categories
        ]

        return success_response(data, 200)

    except Exception as e:
        return error_response(str(e), 500)
