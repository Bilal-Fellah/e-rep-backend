from collections import defaultdict
from datetime import datetime, date
import os
import jwt
from api.repositories.page_history_repository import PageHistoryRepository
from flask import request
from api.repositories.user_repository import UserRepository
from api.routes.main import error_response, success_response
from . import data_bp
from sqlalchemy.exc import SQLAlchemyError

SECRET = os.environ.get("SECRET_KEY")




@data_bp.route("/get_after_time", methods=["GET"])
def get_after_time():
    allowed_roles = ["admin"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        hour = int(request.args.get("hour"))

        history = PageHistoryRepository.get_after_time(hour)
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
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        history = PageHistoryRepository().get_today_all()
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
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        page_id = request.args.get("page_id")

        history = PageHistoryRepository().get_page_data_today(page_id)
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
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        platform = request.args.get("platform")
        if not platform:
            return error_response("Missing platform parameter", 400)

        history_list = PageHistoryRepository().get_platform_history(platform)
        if not history_list:
            return error_response("No history found", 404)

        data = [
            {"id": h.id, "page_id": h.page_id, "data": h.data}
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
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        entity_id = request.args.get("entity_id", type=int)
        date_str = request.args.get("date")  

        allowed_roles = ['admin', 'registered',]
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        role = None
        if payload:
            role = payload['role']
    
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        # parse date
        if date_str:
            try:
                target_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                return error_response("Invalid date format. Use ISO format: YYYY-MM-DD.", 400)
        else:
            target_date = date.today()

        history = PageHistoryRepository().get_entity_data_by_date(entity_id, target_date)
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
    allowed_roles = ["admin", "subscribed", "registered", "public"]
    token = None
    payload = None
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])

    except Exception:
        pass
        print("HHHHHHHHHHHHHHHHHHHHHHH0")

    
    try:
        print("HHHHHHHHHHHHHHHHHHHHHHH1")
        data = PageHistoryRepository.get_all_entities_ranking()
        if not data or (type(data) == list and len(data)<1):
            return error_response("No data found for entities.", 404)
        user = None
        if payload:
            user = UserRepository.get_by_id(payload["user_id"])
        
        print("HHHHHHHHHHHHHHHHHHHHHHH2")
        


        role = user.role if user else 'public'
        if role == 'admin' or role=='subscribed' or role == 'registered':
            return success_response(data, 200)    
        elif role =='public':
            print("HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH3")
            # rank by category
            filter_category = defaultdict(list)
            for row in data:
                filter_category[row['category']].append(row)

            filtered_entities = data[:10]
            for cat in filter_category.keys():
                top_com_here = min(filter_category[cat], key= lambda e: e['rank'], default=None)
                if top_com_here['entity_id'] not in [e['entity_id'] for e in filtered_entities]:
                    filtered_entities.append(top_com_here)

            return success_response(filtered_entities, 200)
       
        else:
            return error_response("Role is not valid", 401)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)















# def get_ranking():
#     try:    
        
#         response = supabase.rpc("get_entity_platform_followers").execute()
        
#         if hasattr(response, "error") and response.error:
#             return error_response(f"Error fetching influence: {getattr(response.error, 'message', str(response.error))}", 500)
#         if not getattr(response, "data", []):
#             return error_response("No influence history found for this page.", 404)
#         data = response.data

#         # Step 1: Aggregate Data per Entity
#         entity_map = defaultdict(lambda: {"total_followers": 0, "platforms": defaultdict(int)})

#         for row in data:
#             entity_id = row["entity_id"]
#             entity_name = row["entity_name"]
#             followers = row["total_followers"]
#             platform = row["platform"]

#             entity_map[entity_id]["entity_name"] = entity_name
#             entity_map[entity_id]["total_followers"] += followers
#             entity_map[entity_id]["platforms"][platform] += followers

#         # Step 2: Convert to List and Rank Entities
#         entities_list = []
#         for entity_id, info in entity_map.items():
#             entities_list.append({
#                 "entity_id": entity_id,
#                 "entity_name": info["entity_name"],
#                 "total_followers": info["total_followers"],
#                 "platforms": dict(info["platforms"])
#             })
            
#         # Step 3: Rank by Total Followers
#         entities_list.sort(key=lambda x: x["total_followers"], reverse=True)
#         for idx, entity in enumerate(entities_list, start=1):
#             entity["rank"] = idx


        
#         return success_response(entities_list, 200)

#     except Exception as e:
#         return error_response(str(e), 500)

