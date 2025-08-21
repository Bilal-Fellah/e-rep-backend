from flask import request
from api.routes.main import error_response, success_response
from api.repositories.page_repository import PageRepository
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

        page = PageRepository.create(
            name=data.get("name", "").strip() or link,  # fallback if name not given
            platform=platform,
            link=link,
            entity_id=entity_id
        )

        return success_response({
            "id": page.id,
            "name": page.name,
            "link": page.link,
            "platform": page.platform,
            "entity_id": page.entity_id
        }, status_code=201)

    except Exception as e:
        return error_response(str(e), status_code=500)


@data_bp.route("/delete_page", methods=["POST"])
def delete_page():
    try:
        page_id = request.json.get("id")
        if not page_id:
            return error_response("Missing required field: 'id'.", status_code=400)

        deleted = PageRepository.delete(page_id)
        if not deleted:
            return error_response(f"No page found with id {page_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": page_id}, status_code=200)

    except Exception as e:
        return error_response(str(e), status_code=500)


@data_bp.route("/get_all_pages", methods=["GET"])
def get_all_pages():
    try:
        pages = PageRepository.get_all()
        if not pages:
            return error_response("No pages found.", status_code=404)

        data = [
            {
                "id": p.id,
                "name": p.name,
                "link": p.link,
                "platform": p.platform,
                "entity_id": p.entity_id
            }
            for p in pages
        ]
        return success_response(data, status_code=200)

    except Exception as e:
        return error_response(str(e), status_code=500)

@data_bp.route("/get_pages_by_platform", methods=["GET"])
def get_pages_by_platform():
    platform = request.args.get("platform")
    try:
        pages = PageRepository.get_by_platform(platform)
        if not pages:
            return error_response("No pages found.", status_code=404)

        data = [
            {
                "id": p.id,
                "name": p.name,
                "link": p.link,
                "platform": p.platform,
                "entity_id": p.entity_id
            }
            for p in pages
        ]
        return success_response(data, status_code=200)

    except Exception as e:
        return error_response(str(e), status_code=500)
