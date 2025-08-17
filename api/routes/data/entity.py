from flask import request
from api.routes.main import error_response, success_response
from api.database.supabase_connection import supabase
from . import data_bp


@data_bp.route("/add_entity", methods=["POST"])
def add_entity():
    try:
        data = request.get_json()
        name = data.get("name", "").strip().lower()
        entity_type = data.get("type", "").strip().lower()
        category_id = data.get("category_id")

        if not name or not entity_type or not category_id:
            return error_response("Missing required fields: 'name', 'type', or 'category_id'.", status=400)

        # Insert entity
        response_entity = supabase.table("entities").insert({
            "name": name,
            "type": entity_type
        }).execute()

        entity_data = getattr(response_entity, "data", None)
        if not entity_data:
            return error_response("Failed to insert entity.", status=500)

        entity = entity_data[0]
        entity_id = entity.get("id")
        if not entity_id:
            return error_response("Entity inserted but no ID returned.", status=500)

        # Link entity to category
        response_link = supabase.table("entity_category").insert({
            "entity_id": entity_id,
            "category_id": category_id
        }).execute()

        link_data = getattr(response_link, "data", None)
        if not link_data:
            return error_response("Failed to insert entity-category relation.", status=500)

        return success_response({
            "entity": entity,
            "entity_category": link_data
        },status_code=201)   # Created

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status=500)


@data_bp.route("/get_all_entities", methods=["GET"])
def get_all_entities():
    try:
        response = supabase.table("entities").select("*").execute()

        entities = getattr(response, "data", None)
        if not entities:
            return error_response("No entities found.", status=404)

        return success_response(entities)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status=500)


@data_bp.route("/delete_entity", methods=["POST"])
def delete_entity():
    try:
        entity_id = request.json.get("id")
        if not entity_id:
            return error_response("Missing required field: 'id'.", status=400)

        # Delete entity-category relations
        supabase.table("entity_category").delete().eq('entity_id', entity_id).execute()

        # Delete entity
        response = supabase.table("entities").delete().eq('id', entity_id).execute()

        deleted_data = getattr(response, "data", None)
        if not deleted_data:
            return error_response(f"No entity found with id {entity_id} or already deleted.", status=404)

        return success_response(deleted_data)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status=500)
