# Data API endpoints for entity.
import os

from flask import request
from api.routes.main import error_response, success_response
from api.services.entity_service import EntityService
from api.utils.permissions import require_role, top_posts_limit_for_role
from . import data_bp

SECRET = os.environ.get("SECRET_KEY")

ALLOWED_ENTITY_TYPES = ("company", "influencer", "small-business")

@data_bp.route("/add_entity", methods=["POST"])
@require_role("admin")
def add_entity():
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip().lower()
        entity_type = data.get("type", "").strip().lower()
        category_id = data.get("category_id")
        pages = data.get("pages")

        if not name or not entity_type or not category_id:
            return error_response("Missing required fields: 'name', 'type', or 'category_id'.", status_code=400)

        if entity_type not in ALLOWED_ENTITY_TYPES:
            return error_response(
                f"type must be one of {list(ALLOWED_ENTITY_TYPES)}.", status_code=400
            )

        if pages is not None and not isinstance(pages, list):
            return error_response("'pages' must be a list.", status_code=400)

        pages_response = None
        if pages:
            # Entity + category + pages are created atomically so a failure
            # can't orphan a half-created entity (see create_entity_with_pages).
            entity, entity_category, pages_response = EntityService.create_entity_with_pages(
                name, entity_type, category_id, pages
            )
        else:
            entity, entity_category = EntityService.create_entity(name, entity_type, category_id)

        response = {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
            },
            "entity_category": {
                "entity_id": entity_category.entity_id,
                "category_id": entity_category.category_id,
            },
        }
        if pages_response is not None:
            response["pages"] = pages_response

        return success_response(response, status_code=201)

    # Page/field validation raises ValueError with a specific, safe message
    # (e.g. "Invalid page platform ...") — surface it instead of a generic 400.
    # IntegrityError (duplicate name / taken page link / bad category) is handled
    # centrally by the blueprint handler as a 409.
    except ValueError as e:
        return error_response(str(e), status_code=400)
    except (TypeError, KeyError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_all_entities", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_all_entities():
    try:
        entities = EntityService.get_all_entities()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type, "to_scrape": e.to_scrape}
            for e in entities
        ]
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_data_existing_entities", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_data_existing_entities():
    try:
        entities = EntityService.get_existing_entities()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
        ]
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/delete_entity", methods=["POST"])
@require_role("admin")
def delete_entity():
    try:
        entity_id = request.json.get("id")
        if not entity_id:
            return error_response("Missing required field: 'id'.", status_code=400)

        deleted = EntityService.delete_entity(entity_id)
        if not deleted:
            return error_response(f"No entity found with id {entity_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": entity_id}, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/update_entity", methods=["POST"])
@require_role("admin")
def update_entity():
    try:
        data = request.get_json() or {}
        entity_id = data.get("id")
        if not entity_id:
            return error_response("Missing required field: 'id'.", status_code=400)
        try:
            entity_id = int(entity_id)
        except (TypeError, ValueError):
            return error_response("'id' must be an integer.", status_code=400)

        name = data.get("name")
        if name is not None:
            name = name.strip().lower()
            if not name:
                return error_response("'name' must be non-empty.", status_code=400)

        entity_type = data.get("type")
        if entity_type is not None:
            entity_type = entity_type.strip().lower()
            if entity_type not in ALLOWED_ENTITY_TYPES:
                return error_response(
                    f"type must be one of {list(ALLOWED_ENTITY_TYPES)}.", status_code=400
                )

        category_id = data.get("category_id")

        entity = EntityService.update_entity(
            entity_id, name=name, entity_type=entity_type, category_id=category_id
        )
        if not entity:
            return error_response(f"No entity found with id {entity_id}.", status_code=404)

        return success_response(
            {"id": entity.id, "name": entity.name, "type": entity.type}, 200
        )

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/set_entity_scrape", methods=["POST"])
@require_role("admin")
def set_entity_scrape():
    """Enable or disable scraping/tracking for an entity ("brand activation")."""
    try:
        data = request.get_json() or {}
        entity_id = data.get("id")
        to_scrape = data.get("to_scrape")
        if not entity_id or to_scrape is None:
            return error_response(
                "Missing required fields: 'id' and 'to_scrape'.", status_code=400
            )
        try:
            entity_id = int(entity_id)
        except (TypeError, ValueError):
            return error_response("'id' must be an integer.", status_code=400)
        if not isinstance(to_scrape, bool):
            return error_response("'to_scrape' must be a boolean.", status_code=400)

        entity = EntityService.set_entity_scrape(entity_id, to_scrape)
        if not entity:
            return error_response(f"No entity found with id {entity_id}.", status_code=404)

        return success_response(
            {"id": entity.id, "to_scrape": entity.to_scrape}, 200
        )

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_entity_profile_card", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_profile_card():
    try:
        entity_id = request.args.get("entity_id")
        data = EntityService.get_entity_profile_card(entity_id)
        if type(data) != dict:
            if type(data) == list and len(data) < 1:
                message = "no data found for this entity"
                return error_response(message, status_code=404)

        return success_response(data, status_code=200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_entity_followers_history", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_followers_history():
    """
    Fetch all page histories for a given entity_id (all pages belonging to entity).
    Optional: filter by date (default = today).
    """
    try:
        entity_id = request.args.get("entity_id", type=int)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        data = EntityService.get_entity_followers_history(entity_id)
        if not data or (type(data) == list and len(data)<1):
            return error_response("No history found for this entity.", 404)
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/compare_entities_followers", methods=['POST'])
@require_role("admin", "registered", "subscribed")
def compare_entities_followers():
    try:
        data = request.get_json(silent=True) or {}
        entity_ids = data.get("entity_ids")
        if not isinstance(entity_ids, list) or not entity_ids:
            return error_response("Missing required key: 'entity_ids'.", 400)

        data = EntityService.compare_entities_followers(entity_ids)
        if not data or len(data) < 1:
            return error_response("No data for this entities", 404)
        return success_response(data, 200)
        # we get the entities or category

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_entity_likes_history", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_likes_history():
    try:
        entity_id = request.args.get("entity_id", type=int)
        start_date = request.args.get("start_date")

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        data = EntityService.get_entity_likes_history(entity_id, start_date=start_date)
        if not data or (type(data) == list and len(data) < 1):
            return error_response("No likes development found for this entity.", 404)

        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/compare_entities_likes", methods=['POST'])
@require_role("admin", "registered", "subscribed")
def compare_entities_likes():
    try:
        payload = request.get_json(silent=True) or {}
        entity_ids = payload.get("entity_ids")
        start_date = payload.get("start_date")

        if not isinstance(entity_ids, list) or not entity_ids:
            return error_response("Missing required key: 'entity_ids'.", 400)

        data = EntityService.compare_entities_likes(entity_ids, start_date=start_date)
        if not data or len(data) < 1:
            return error_response("No likes development data for this entities", 404)

        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_entity_comments_history", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_comments_history():
    try:
        entity_id = request.args.get("entity_id", type=int)
        start_date = request.args.get("start_date")

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        data = EntityService.get_entity_comments_history(entity_id, start_date=start_date)
        if not data or (type(data) == list and len(data) < 1):
            return error_response("No comments development found for this entity.", 404)

        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/compare_entities_comments", methods=['POST'])
@require_role("admin", "registered", "subscribed")
def compare_entities_comments():
    try:
        payload = request.get_json(silent=True) or {}
        entity_ids = payload.get("entity_ids")
        start_date = payload.get("start_date")

        if not isinstance(entity_ids, list) or not entity_ids:
            return error_response("Missing required key: 'entity_ids'.", 400)

        data = EntityService.compare_entities_comments(entity_ids, start_date=start_date)
        if not data or len(data) < 1:
            return error_response("No comments development data for this entities", 404)

        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

@data_bp.route("/get_entity_posts_timeline", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_posts_timeline():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        entity_id = request.args.get("entity_id", type=int)
        date_str = request.args.get("date")
        max_posts = request.args.get("max_posts", type=int)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        try:
            all_posts = EntityService.get_entity_posts_timeline(entity_id, date_str=date_str, max_posts=max_posts)
        except ValueError:
            return error_response("Invalid date format provided.", 400)

        if not all_posts or (type(all_posts) == list and len(all_posts) < 1):
            return error_response("No history found for this entity.", 404)

        return success_response(all_posts, 200)


    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/mark_entity_to_scrape", methods=["GET"])
@require_role("admin")
def mark_entity_to_scrape():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        entity_id = request.args.get("entity_id", type=int)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        res = EntityService.mark_entity_to_scrape(entity_id)

        return success_response({"message": f"{res}", "entity_id": entity_id}, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)

# a route that returns top k performing posts for an entity
@data_bp.route("/get_entity_top_posts", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_entity_top_posts():
    try:
        entity_id = request.args.get("entity_id", type=int)
        k = request.args.get("top_posts", type=int, default=5)
        date = request.args.get("date")

        # Free (registered) users only get the single top post (top_posts rule).
        role = getattr(request, "user_role", None)
        k = top_posts_limit_for_role(role, k)

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        day_gains, _posts_num, _skipped = EntityService.get_entity_top_posts(entity_id, date, k)

        return success_response(day_gains, 200)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
