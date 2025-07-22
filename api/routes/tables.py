# # app/routes/myworker.py

# from flask import Blueprint, jsonify, request
# from api.db.connection import supabase

# data_bp = Blueprint("data", __name__)


# def error_response(message, status=400):
#     return jsonify({"success": False, "error": message}), status


# def success_response(data):
#     return jsonify({"success": True, "data": data})


# @data_bp.route("/add_entity", methods=["POST"])
# def add_entity():
#     try:
#         data = request.get_json()
#         name = data.get("name", "").strip().lower()
#         entity_type = data.get("type", "").strip().lower()
#         category_id = data.get("category_id")

#         if not name or not entity_type or not category_id:
#             return error_response("Missing required fields: 'name', 'type', or 'category_id'.")

#         # Insert entity
#         add_entity_response = supabase.table("entities").insert({
#             "name": name,
#             "type": entity_type
#         }).execute()

#         if not add_entity_response.data or not isinstance(add_entity_response.data, list):
#             return error_response(f"Failed to insert entity: {add_entity_response.details or add_entity_response.message} .")

#         entity = add_entity_response.data[0]
#         entity_id = entity.get("id")
#         if not entity_id:
#             return error_response("Entity inserted but no ID returned.")

#         # Insert category relation
#         add_category_relation_response = supabase.table("entity_category").insert({
#             "entity_id": entity_id,
#             "category_id": category_id
#         }).execute()

#         if not add_category_relation_response.data:
#             return error_response("Failed to insert entity-category relation.")

#         return success_response({
#             "entity": entity,
#             "entity_category": add_category_relation_response.data
#         })

#     except Exception as e:
#         return error_response(str(e))
    
# @data_bp.route("/get_all_entities", methods=["GET"])
# def get_all_entities():
#     try:
       
#         get_entities_response = supabase.table("entities").select("*").execute()
        
#         if not get_entities_response.data or not isinstance(get_entities_response.data, list):
#             return error_response(f"Failed to get entities: {get_entities_response.details or get_entities_response.message} .")       
#         print(get_entities_response.data)
#         return success_response({
#             "entities": get_entities_response.data,
#         })

#     except Exception as e:
#         return error_response(str(e))
    


# @data_bp.route("/delete_entity", methods=["POST"])
# def delete_entity():
#     try:
#         entity_id = request.json.get("id")
#         if not entity_id:
#             return error_response("Missing required field: 'id'.")

#         # First delete entity-category relation(s)
#         delete_relation_response = supabase.table("entity_category").delete().eq('entity_id', entity_id).execute()

#         # Then delete the entity itself
#         delete_entity_response = supabase.table("entities").delete().eq('id', entity_id).execute()

#         if not delete_entity_response.data:
#             return error_response(f"No entity found with id {entity_id} or already deleted.")

#         return success_response({
#             "entity_deleted": delete_entity_response.data,
#             "relations_deleted": delete_relation_response.data
#         })

#     except Exception as e:
#         return error_response(str(e))



# @data_bp.route("/add_category", methods=["POST"])
# def add_category():
#     try:
#         data = request.get_json()
#         name = data.get("name", "").strip().lower()
#         parent_id = data.get("parent_id")

#         if not name:
#             return error_response("Missing required field: 'name'.")

#         response = supabase.table("categories").insert({
#             "name": name,
#             "parent_id": parent_id
#         }).execute()

#         if not response.data:
#             return error_response("Failed to insert category.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))


# @data_bp.route("/delete_category", methods=["POST"])
# def delete_category():
#     try:
#         id = request.json.get("id")
#         if not id:
#             return error_response("Missing required field: 'id'.")

#         response = supabase.table("categories").delete().eq('id', id).execute()

#         if not response.data:
#             return error_response(f"No category found with id {id} or already deleted.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))

# @data_bp.route("/get_all_categories", methods=["GET"])
# def get_all_categories():
#     try:
#         response = supabase.table("categories").select("*").execute()

#         if not response.data:
#             return error_response("No categories found.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))


# @data_bp.route("/add_page", methods=["POST"])
# def add_page():
#     try:
#         data = request.get_json()
#         platform = data.get("platform", "").strip().lower()
#         link = data.get("link", "").strip().lower()
#         entity_id = data.get("entity_id")

#         if not platform or not link or not entity_id:
#             return error_response("Missing required fields: 'platform', 'link', or 'entity_id'.")

#         response = supabase.table("pages").insert({
#             "platform": platform,
#             "link": link,
#             "entity_id": entity_id
#         }).execute()

#         if not response.data:
#             return error_response("Failed to insert page.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))


# @data_bp.route("/delete_page", methods=["POST"])
# def delete_page():
#     try:
#         id = request.json.get("id")
#         if not id:
#             return error_response("Missing required field: 'id'.")

#         response = supabase.table("pages").delete().eq('id', id).execute()

#         if not response.data:
#             return error_response(f"No page found with id {id} or already deleted.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))
    
# @data_bp.route("/get_all_pages", methods=["GET"])
# def get_all_pages():
#     try:
#         response = supabase.table("pages").select("*").execute()

#         if not response.data:
#             return error_response("No pages found.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))



# @data_bp.route("/add_influence", methods=["POST"])
# def add_influence():
#     try:
#         data = request.get_json()
#         page_id = data.get("page_id")
#         followers = data.get("followers")
#         likes = data.get("likes")
#         recorded_at = data.get("recorded_at")  # Optional

#         if not page_id or followers is None or likes is None:
#             return error_response("Missing required fields: 'page_id', 'followers', or 'likes'.")

#         influence_data = {
#             "page_id": page_id,
#             "followers": followers,
#             "likes": likes
#         }

#         if recorded_at:
#             influence_data["recorded_at"] = recorded_at

#         response = supabase.table("influence_history").insert(influence_data).execute()

#         data = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
#         if not data:
#             return error_response("Failed to insert influence record.")

#         return success_response(data)

#     except Exception as e:
#         return error_response(str(e))


# @data_bp.route("/get_influence_history", methods=["GET"])
# def get_influence_history():
#     try:
#         response = supabase.table("influence_history").select("*").execute()

#         if not response.data:
#             return error_response("No history found for influence.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))


# @data_bp.route("/get_page_influence", methods=["GET"])
# def get_page_influence():
#     try:
#         page_id = request.args.get("page_id")
#         response = supabase.table("influence_history").select("*").eq('page_id', page_id).execute()

#         if not response.data:
#             return error_response("No history found for influence.")

#         return success_response(response.data)

#     except Exception as e:
#         return error_response(str(e))
