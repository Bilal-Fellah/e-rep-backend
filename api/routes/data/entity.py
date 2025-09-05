from collections import defaultdict
from api.repositories.page_history_repository import PageHistoryRepository
from flask import request, jsonify
from api.routes.main import error_response, success_response
from api.repositories.entity_repository import EntityRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from sqlalchemy.exc import SQLAlchemyError

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


@data_bp.route("/get_entity_profile_card", methods=["GET"])
def get_entity_profile_card():


    try:
        entity_id = request.args.get("entity_id")
        data = PageHistoryRepository.get_entity_info_from_history(entity_id)
        if type(data) != dict:
            if type(data) == list and len(data) < 1:
                message = "no data found for this entity"
                return error_response(message, status_code=404) 
            
        return success_response(data, status_code=200)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/get_entity_followers_history", methods=["GET"])
def get_entity_followers_history():
    """
    Fetch all page histories for a given entity_id (all pages belonging to entity).
    Optional: filter by date (default = today).
    """
    try:
        entity_id = request.args.get("entity_id", type=int)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        history = PageHistoryRepository().get_followers_history_by_entity(entity_id)
        if not history or (type(history) == list and len(history)<1):
            return error_response("No history found for this entity.", 404)

        data = [{'page_id': h.page_id, 'followers': h.followers, 'date': h.recorded_at, "platform": h.platform} for h in history]
        return success_response(data, 200)

    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
    



@data_bp.route("/get_entity_recent_posts", methods=["GET"])
def get_entity_recent_posts():
    """
    get recent posts (5) from all platforms, get the most recent
    """
    try:
        entity_id = request.args.get("entity_id", type=int)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        history = PageHistoryRepository().get_entity_recent_posts(entity_id)
        if not history or (type(history) == list and len(history)<1):
            return error_response("No history found for this entity.", 404)

        return success_response(history, 200)

    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
    
   
@data_bp.route("/get_entity_followers_comparison", methods=["GET"])
def get_entity_followers_comparison():
    try:
        entity_id = request.args.get("entity_id")
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)
        raw_results = PageHistoryRepository.get_category_followers_competition(entity_id)

        if not raw_results or len(raw_results) < 1:
            return error_response("No data for this entity", 404)

        data = defaultdict(lambda: defaultdict(list))

        for row in raw_results:
            if row.entity_name:
                data[row.entity_name]["entity_id"] = row.entity_id

            data[row.entity_name][row.platform].append({
                "recorded_at": row.recorded_at.isoformat(),
                "followers": row.followers,
                "page_id": row.page_id,
            })
        return success_response(data)
        # we get the entities or category
    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
