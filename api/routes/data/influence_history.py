from flask import request
from api.routes.main import error_response, success_response
from api.db.connection import supabase
from . import data_bp


@data_bp.route("/add_influence", methods=["POST"])
def add_influence():
    try:
        data = request.get_json()
        page_id = data.get("page_id")
        followers = data.get("followers")
        likes = data.get("likes")
        recorded_at = data.get("recorded_at")  # Optional

        if not page_id or followers is None or likes is None:
            return error_response("Missing required fields: 'page_id', 'followers', or 'likes'.", 400)

        payload = {
            "page_id": page_id,
            "followers": followers,
            "likes": likes
        }

        if recorded_at:
            payload["recorded_at"] = recorded_at

        response = supabase.table("influence_history").insert(payload).execute()

        if hasattr(response, "error") and response.error:
            return error_response(f"Failed to insert influence record: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("Insert succeeded but returned no data.", 204)

        return success_response(response.data, 201)

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_influence_history", methods=["GET"])
def get_influence_history():
    try:
        response = supabase.table("influence_history").select("*").execute()

        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence history: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found.", 404)

        return success_response(response.data, 200)

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_page_influence", methods=["GET"])
def get_page_influence():
    try:
        page_id = request.args.get("page_id")
        if not page_id:
            return error_response("Missing required query param: 'page_id'.", 400)

        response = supabase.table("influence_history").select("*").eq('page_id', page_id).execute()

        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found for this page.", 404)

        return success_response(response.data, 200)

    except Exception as e:
        return error_response(str(e), 500)
