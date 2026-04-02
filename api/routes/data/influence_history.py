from datetime import datetime
import os
import jwt
from flask import request
from api.routes.main import error_response, success_response
from api.services.influence_history_service import InfluenceHistoryService
from api.utils.auth import _extract_token
from . import data_bp
from sqlalchemy.exc import SQLAlchemyError
import traceback


SECRET = os.environ.get("SECRET_KEY")


@data_bp.route("/get_after_time", methods=["GET"])
def get_after_time():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        hour = int(request.args.get("hour"))

        history = InfluenceHistoryService.get_after_time(hour)
        if not history:
            return error_response("No history found", 404)
        
        data = [{'id': h.id, 'page_id': h.page_id, 'data': h.data} for h in history ]
        return success_response(data, 200)

    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)

@data_bp.route("/get_today_pages_history", methods=["GET"])
def get_today_pages_history():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        history = InfluenceHistoryService.get_today_pages_history()
        if not history:
            return error_response("No history found", 404)
        
        data = [{'id': h.id, 'page_id': h.page_id, 'data': h.data} for h in history ]
        return success_response(data, 200)

    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_page_history_today", methods=["GET"])
def get_page_history():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        page_id = request.args.get("page_id")

        history = InfluenceHistoryService.get_page_history_today(page_id)
        if not history:
            return error_response("No history found", 404)
        
        data = {'id': history.id, 'page_id': history.page_id, 'data': history.data}
        return success_response(data, 200)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_platform_history", methods=["GET"])
def get_platform_history():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        platform = request.args.get("platform")
        if not platform:
            return error_response("Missing platform parameter", 400)
        print(platform)
        history_list = InfluenceHistoryService.get_platform_history(platform)
        if not history_list:
            return error_response("No history found", 404)

        data = [
            {"id": h.id, "page_id": h.page_id, "data": h.data, "recorded_at": h.recorded_at}
            for h in history_list
        ]
        return success_response(data, 200)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_entity_history", methods=["GET"])
def get_entity_history():
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
        date_str = request.args.get("date")  

        token = _extract_token("access_token")
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        if payload:
            payload['role']
    
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except ValueError:
                return error_response("Invalid date format. Use ISO format: YYYY-MM-DD.", 400)

        history = InfluenceHistoryService.get_entity_history(entity_id, date_str=date_str)
        if not history:
            return error_response("No history found for this entity.", 404)
        
        data = [{'id': h.id, 'page_id': h.page_id, 'data': h.data, 'date': h.recorded_at} for h in history]
        return success_response(data, 200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)

    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
    

@data_bp.route("/get_entities_ranking", methods=["GET"])
def get_entities_ranking():
    # try:
    #     token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    #     payload = jwt.decode(token, SECRET, algorithms=['HS256'])

    # except Exception:
    #     pass
    
    try:

        data = InfluenceHistoryService.get_entities_ranking()


        if not data or (type(data) == list and len(data)<1):
            return error_response("No data found for entities.", 404)
        
        # user = None
        # if payload:
        #     user = UserRepository.get_by_id(payload["user_id"])

        # role = user.role if user else 'public'
        
        # if role == 'admin' or role=='subscribed' or role == 'registered':
        return success_response(data, 200)    
        
        # elif role =='public':
        #     # rank by category
        #     filter_category = defaultdict(list)
        #     for row in data:
        #         filter_category[row['category']].append(row)

        #     filtered_entities = data[:10]
        #     for cat in filter_category.keys():
        #         top_com_here = min(filter_category[cat], key= lambda e: e['rank'], default=None)
        #         if top_com_here['entity_id'] not in [e['entity_id'] for e in filtered_entities]:
        #             filtered_entities.append(top_com_here)

        #     return success_response(filtered_entities, 200)
       
        # else:
        #     return error_response("Role is not valid", 401)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/entities_ranking", methods=['GET'])
def entities_ranking():
    return success_response(InfluenceHistoryService.entities_ranking(), 200)


@data_bp.route("/get_entity_interaction_stats", methods=["GET"])
def get_entity_interaction_stats():
    try:
        entity_id = request.args.get("entity_id", type=int)
        start_date = request.args.get("start_date")
        if start_date:
            start_date = datetime.fromisoformat(start_date)

        data = InfluenceHistoryService.get_entity_interaction_stats(entity_id, start_date=start_date)
        if not data:
            return error_response(f"No data found for entity {entity_id}.", 404)
        return success_response(data, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", 500)


@data_bp.route("/get_competitors_interaction_stats", methods=["POST"])
def get_competitors_interaction_stats():

    try:
        inputs = request.get_json()

        entity_ids = list(inputs.get("entity_ids"))
        if not entity_ids:
            return error_response(f"wrong value for entity_ids")
        
        start_date = inputs.get("start_date", None)
        # print(start_date)

        if start_date:
            start_date = ensure_datetime(start_date)
        else:
            start_date = None

        if not isinstance(entity_ids, list):
            return error_response(f"entity_ids must be a list not a {type(entity_ids)}")
        
        data = InfluenceHistoryService.get_competitors_interaction_stats(entity_ids, start_date=start_date)

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(f"No data found for entity {entity_ids}.", 404)
        return success_response(data, 200)

    except Exception as e:
        traceback.print_exc()
        return error_response(f"Internal server error: {str(e)}", 500)
