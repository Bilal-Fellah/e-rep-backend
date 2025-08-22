from flask import request, jsonify
from api.routes.main import error_response, success_response
from api.repositories.entity_repository import EntityRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from . import data_bp


@data_bp.route("/add_entity", methods=["POST"])
def add_entity():
    try:
        data = request.get_json()
        name = data.get("name", "").strip().lower()
        entity_type = data.get("type", "").strip().lower()
        category_id = data.get("category_id")

        if not name or not entity_type or not category_id:
            return error_response("Missing required fields: 'name', 'type', or 'category_id'.", status_code=400)

        # Insert entity
        entity = EntityRepository.create(name=name, type_=entity_type)

        # Link entity to category
        entity_category = EntityCategoryRepository.add(entity_id=entity.id, category_id=category_id)

        return success_response({
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
            },
            "entity_category": {
                "entity_id": entity_category.entity_id,
                "category_id": entity_category.category_id,
            }
        }, status_code=201)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)


@data_bp.route("/get_all_entities", methods=["GET"])
def get_all_entities():
    try:
        entities = EntityRepository.get_all()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
        ]
        return success_response(data, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)


@data_bp.route("/delete_entity", methods=["POST"])
def delete_entity():
    try:
        entity_id = request.json.get("id")
        if not entity_id:
            return error_response("Missing required field: 'id'.", status_code=400)

        # Delete entity-category relations
        EntityCategoryRepository.delete_by_entity(entity_id)

        # Delete entity
        deleted = EntityRepository.delete(entity_id)
        if not deleted:
            return error_response(f"No entity found with id {entity_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": entity_id}, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)


