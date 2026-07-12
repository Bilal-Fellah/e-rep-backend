# Data API endpoints for page.
from flask import request
from api.routes.main import error_response, success_response
from api.services.page_service import PageService
from api.utils.permissions import require_role
from . import data_bp
import os

SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_page", methods=["POST"])
@require_role("admin")
def add_page():
    try:
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
@require_role("admin")
def delete_page():
    try:
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
@require_role("admin", "registered", "subscribed")
def get_all_pages():
    try:
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
@require_role("admin", "registered", "subscribed")
def get_pages_by_platform():
    try:
        platform = request.args.get("platform")
        if not platform:
            return error_response("Missing required query param: 'platform'.", 400)

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
