from flask import request
from api.routes.main import error_response, success_response
from api.db.connection import supabase
from . import data_bp


# @data_bp.route("/add_category", methods=["POST"])
# def add_category():
#     try:
#         data = request.get_json()
#         name = data.get("name", "").strip().lower()
#         parent_id = data.get("parent_id")

#         if not name:
#             return error_response("Missing required field: 'name'.", 400)

#         response = supabase.table("categories").insert({
#             "name": name,
#             "parent_id": parent_id
#         }).execute()

#         error = getattr(response, "error", None)
#         if error:
#             return error_response(f"Failed to insert category: {error.message}", 400)

#         data = getattr(response, "data", None)
#         if not data:
#             return error_response("Insert succeeded but returned no data.", 500)

#         return success_response(data, 201)

#     except Exception as e:
#         return error_response(str(e), 500)


# @data_bp.route("/delete_category", methods=["POST"])
# def delete_category():
#     try:
#         id = request.json.get("id")
#         if not id:
#             return error_response("Missing required field: 'id'.", 400)

#         response = supabase.table("categories").delete().eq('id', id).execute()

#         error = getattr(response, "error", None)
#         if error:
#             return error_response(f"Delete failed: {error.message}", 400)

#         data = getattr(response, "data", None)
#         if not data:
#             return error_response(f"No category found with id {id} or already deleted.", 404)

#         return success_response(data, 200)

#     except Exception as e:
#         return error_response(str(e), 500)


# @data_bp.route("/get_all_categories", methods=["GET"])
# def get_all_categories():
#     try:
#         response = supabase.table("categories").select("*").execute()

#         error = getattr(response, "error", None)
#         if error:
#             return error_response(f"Error fetching categories: {error.message}", 500)

#         data = getattr(response, "data", None)
#         if not data:
#             return error_response("No categories found.", 404)

#         return success_response(data, 200)

#     except Exception as e:
#         return error_response(str(e), 500)
