# Data API endpoints for category.
from flask import request
from api.routes.main import error_response, success_response
from api.repositories.category_repository import CategoryRepository
from api.utils.permissions import require_role
from . import data_bp


def _serialize_category(category):
    return {
        "id": category.id,
        "name": category.name,
        "name_french": category.name_french,
        "parent_id": category.parent_id,
        "is_active": category.is_active,
        "applicable_to": category.applicable_to,
    }

@data_bp.route("/add_category", methods=["POST"])
@require_role("admin")
def add_category():
    try:
        data = request.get_json()
        name = data.get("name", "").strip().lower()
        name_french = data.get("name_french")
        if isinstance(name_french, str):
            name_french = name_french.strip().lower() or None
        parent_id = data.get("parent_id")
        applicable_to = data.get("applicable_to", "company").strip().lower()
        
        if applicable_to not in ("company", "influencer"):
            return error_response("'applicable_to' must be one of ['company', 'influencer'].", 400)

        if not name:
            return error_response("Missing required field: 'name'.", 400)

        category = CategoryRepository.create(name=name, name_french=name_french, parent_id=parent_id, applicable_to=applicable_to)
        return success_response(_serialize_category(category), 201)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
    

@data_bp.route("/delete_category", methods=["POST"])
@require_role("admin")
def delete_category():
    try:
        category_id = request.json.get("id")
        if not category_id:
            return error_response("Missing required field: 'id'.", 400)

        deleted = CategoryRepository.delete(category_id)
        if not deleted:
            return error_response(f"No category found with id {category_id}", 404)

        return success_response({"deleted_id": category_id}, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/update_category", methods=["POST"])
@require_role("admin")
def update_category():
    """Edit a category's fields and/or toggle is_active (admin only)."""
    try:
        data = request.get_json() or {}
        category_id = data.get("id")
        if not category_id:
            return error_response("Missing required field: 'id'.", 400)
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return error_response("'id' must be an integer.", 400)

        fields = {}
        name = data.get("name")
        if name is not None:
            name = name.strip().lower()
            if not name:
                return error_response("'name' must be non-empty.", 400)
            fields["name"] = name

        if "name_french" in data:
            name_french = data.get("name_french")
            if isinstance(name_french, str):
                name_french = name_french.strip().lower() or None
            fields["name_french"] = name_french

        if "parent_id" in data:
            parent_id = data.get("parent_id")
            if parent_id is not None:
                try:
                    parent_id = int(parent_id)
                except (TypeError, ValueError):
                    return error_response(
                        "'parent_id' must be an integer or null.", 400
                    )
                # Reject self-parenting and cycles: walk up from the proposed
                # parent; if we reach this category, the tree would loop.
                if parent_id == category_id:
                    return error_response(
                        "A category cannot be its own parent.", 400
                    )
                cursor, seen = parent_id, set()
                while cursor is not None:
                    if cursor == category_id:
                        return error_response(
                            "This change would create a category cycle.", 400
                        )
                    if cursor in seen:
                        break  # pre-existing loop elsewhere; stop walking
                    seen.add(cursor)
                    ancestor = CategoryRepository.get_by_id(cursor)
                    cursor = ancestor.parent_id if ancestor else None
            fields["parent_id"] = parent_id

        if "is_active" in data:
            is_active = data.get("is_active")
            if not isinstance(is_active, bool):
                return error_response("'is_active' must be a boolean.", 400)
            fields["is_active"] = is_active

        if "applicable_to" in data:
            applicable_to = data.get("applicable_to")
            if applicable_to not in ("company", "influencer"):
                return error_response("'applicable_to' must be one of ['company', 'influencer'].", 400)
            fields["applicable_to"] = applicable_to

        category = CategoryRepository.update(category_id, **fields)
        if not category:
            return error_response(f"No category found with id {category_id}", 404)

        return success_response(_serialize_category(category), 200)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_all_categories", methods=["GET"])
def get_all_categories():
    try:
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


@data_bp.route("/get_active_categories_by_type", methods=["GET"])
def get_active_categories_by_type():
    """Get active categories filtered by entity type (company or influencer)."""
    try:
        applicable_to = request.args.get("applicable_to", "company").strip().lower()
        if applicable_to not in ("company", "influencer"):
            return error_response("'applicable_to' must be one of ['company', 'influencer'].", 400)

        categories = CategoryRepository.get_all_active_by_type(applicable_to)
        if not categories:
            return error_response(f"No active categories found for type '{applicable_to}'.", 404)

        data = [_serialize_category(category) for category in categories]
        return success_response(data, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


