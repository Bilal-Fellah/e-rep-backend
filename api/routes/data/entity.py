import os

from flask import request
from api.routes.main import error_response, success_response
from api.services.entity_service import EntityService
from . import data_bp


SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_entity", methods=["POST"])
def add_entity():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:   
        #     return error_response("Access denied", 403)
        
        data = request.get_json()
        name = data.get("name", "").strip().lower()
        entity_type = data.get("type", "").strip().lower()
        category_id = data.get("category_id")

        if not name or not entity_type or not category_id:
            return error_response("Missing required fields: 'name', 'type', or 'category_id'.", status_code=400)

        entity, entity_category = EntityService.create_entity(name, entity_type, category_id)

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
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_all_entities", methods=["GET"])
def get_all_entities():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entities = EntityService.get_all_entities()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
        ]
        return success_response(data, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_data_existing_entities", methods=["GET"])
def get_data_existing_entities():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
def delete_entity():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entity_id = request.json.get("id")
        if not entity_id:
            return error_response("Missing required field: 'id'.", status_code=400)

        deleted = EntityService.delete_entity(entity_id)
        if not deleted:
            return error_response(f"No entity found with id {entity_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": entity_id}, 200)
    
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", status_code=400)

@data_bp.route("/get_entity_profile_card", methods=["GET"])
def get_entity_profile_card():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
def get_entity_followers_history():
    """
    Fetch all page histories for a given entity_id (all pages belonging to entity).
    Optional: filter by date (default = today).
    """
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

        data = EntityService.get_entity_followers_history(entity_id)
        if not data or (type(data) == list and len(data)<1):
            return error_response("No history found for this entity.", 404)
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
   
# @data_bp.route("/get_entity_followers_comparison", methods=["GET"])
# def get_entity_followers_comparison():
#     allowed_roles = ["admin", "subscribed", "registered"]

#     try:
#         # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
#         # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
#         # if not payload:
#         #     return error_response("No valid token has been sent", 401)
#         # role = payload['role']
#         # if role not in allowed_roles:
#         #     return error_response("Access denied", 403)
        
#         entity_id = request.args.get("entity_id")
#         if not entity_id:
#             return error_response("Missing required query param: 'entity_id'.", 400)
#         raw_results = PageHistoryRepository.get_category_followers_competition(entity_id)

#         if not raw_results or len(raw_results) < 1:
#             return error_response("No data for this entity", 404)


#         data = defaultdict(lambda: {"entity_id": None, "records": []})

#         for idx, row in enumerate(raw_results):
#             if row.entity_name:
#                 if data[row.entity_name]["entity_id"] is None:
#                     data[row.entity_name]["entity_id"] = row.entity_id

#                 date = row.recorded_at.date().isoformat()
#                 platform = row.platform
#                 followers = row.followers
#                 mistakes = []
#                 # sum directly by date (all platforms included)
#                 if followers:
#                     data[row.entity_name]["records"].append({
#                         'date': date,
#                         'platform': platform,
#                         'followers': followers
#                     }
#                     )
#                 else:
#                     mistakes.append(row.followers)
#         return success_response(data, 200)
#         # we get the entities or category
#     except SQLAlchemyError as e:
#         return error_response(f"Database error: {str(e)}", 500)
#     except jwt.ExpiredSignatureError:
#         return error_response("Token has expired", 401)
#     except jwt.InvalidTokenError:
#         return error_response("Invalid token", 401)
#     except Exception as e:
#         return error_response(f"Unexpected error: {str(e)}", 500)

@data_bp.route("/compare_entities_followers", methods=['POST'])
def compare_entities_followers():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
def get_entity_top_posts():
    try:    
        entity_id = request.args.get("entity_id", type=int)
        k = request.args.get("top_posts", type=int, default=5)
        date = request.args.get("date") 


        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)
        
        day_gains, _posts_num, _skipped = EntityService.get_entity_top_posts(entity_id, date, k)

        return success_response(day_gains, 200)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


