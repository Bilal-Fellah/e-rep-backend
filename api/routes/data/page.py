from flask import request
from api.routes.main import error_response, success_response
from api.db.connection import supabase
from . import data_bp


@data_bp.route("/add_page", methods=["POST"])
def add_page():
    try:
        data = request.get_json()
        platform = data.get("platform", "").strip().lower()
        link = data.get("link", "").strip().lower()
        entity_id = data.get("entity_id")

        if not platform or not link or not entity_id:
            return error_response("Missing required fields: 'platform', 'link', or 'entity_id'.", status_code=400)

        response = supabase.table("pages").insert({
            "platform": platform,
            "link": link,
            "entity_id": entity_id
        }).execute()

        error = getattr(response, "error", None)
        data = getattr(response, "data", None)

        if error:
            return error_response(f"Failed to insert page: {error.message}", status_code=500)
        if not data:
            return error_response("Insert succeeded but returned no data.", status_code=204)

        return success_response(data, status_code=201)

    except Exception as e:
        return error_response(str(e), status_code=500)


@data_bp.route("/delete_page", methods=["POST"])
def delete_page():
    try:
        id = request.json.get("id")
        if not id:
            return error_response("Missing required field: 'id'.", status_code=400)

        response = supabase.table("pages").delete().eq('id', id).execute()

        error = getattr(response, "error", None)
        data = getattr(response, "data", None)

        if error:
            return error_response(f"Delete failed: {error.message}", status_code=500)
        if not data:
            return error_response(f"No page found with id {id} or already deleted.", status_code=404)

        return success_response(data, status_code=200)

    except Exception as e:
        return error_response(str(e), status_code=500)


@data_bp.route("/get_all_pages", methods=["GET"])
def get_all_pages():
    try:
        response = supabase.table("pages").select("*").execute()

        error = getattr(response, "error", None)
        data = getattr(response, "data", None)

        if error:
            return error_response(f"Error fetching pages: {error.message}", status_code=500)
        if not data:
            return error_response("No pages found.", status_code=404)

        return success_response(data, status_code=200)

    except Exception as e:
        return error_response(str(e), status_code=500)
