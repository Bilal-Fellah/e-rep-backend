from flask import request
from api.routes.main import error_response, success_response
from api.services.page_service import PageService
from . import data_bp
import os

SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_page", methods=["POST"])
def add_page():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        data = request.get_json()
        page, error_message = PageService.create_page(data)
        if error_message:
            return error_response(error_message, status_code=400)

        return success_response({
            "uuid": str(page.uuid),  # Convert the UUID object to a string for the response
            "name": page.name,
            "link": page.link,
            "platform": page.platform,
            "entity_id": page.entity_id
        }, status_code=201)



    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/delete_page", methods=["POST"])
def delete_page():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        page_id = request.json.get("id")
        if not page_id:
            return error_response("Missing required field: 'id'.", status_code=400)

        deleted = PageService.delete_page(page_id)
        if not deleted:
            return error_response(f"No page found with id {page_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": page_id}, status_code=200)


    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_all_pages", methods=["GET"])
def get_all_pages():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        pages = PageService.get_all_pages()
        if not pages:
            return error_response("No pages found.", status_code=404)

        data = [
            {
                "name": p.name,
                "link": p.link,
                "platform": p.platform,
                "entity_id": p.entity_id,
                "uuid": p.uuid
            }
            for p in pages
        ]
        return success_response(data, status_code=200)


    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/get_pages_by_platform", methods=["GET"])
def get_pages_by_platform():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        platform = request.args.get("platform")
        pages = PageService.get_pages_by_platform(platform)
        if not pages:
            return error_response("No pages found.", status_code=404)

        data = [
            {
                "uuid": p.uuid,
                "name": p.name,
                "link": p.link,
                "platform": p.platform,
                "entity_id": p.entity_id
            }
            for p in pages
        ]
        return success_response(data, status_code=200)


    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/get_page_interaction_stats", methods=["GET"])
def get_page_interaction_stats():
    try:
        page_id = request.args.get("page_id")
        start_date = request.args.get("start_date")
        data = PageService.get_page_interaction_stats(page_id, start_date)

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(f"No data found for page {page_id}.", 404)
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
