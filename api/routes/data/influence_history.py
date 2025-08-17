from collections import defaultdict
from datetime import datetime
from flask import request
from api.routes.main import error_response, success_response
from api.database.supabase_connection import supabase
from . import data_bp


# @data_bp.route("/add_influence", methods=["POST"])
# def add_influence():
#     try:
#         data = request.get_json()
#         page_id = data.get("page_id")
#         followers = data.get("followers")
#         likes = data.get("likes")
#         recorded_at = data.get("recorded_at")  # Optional

#         if not page_id or followers is None or likes is None:
#             return error_response("Missing required fields: 'page_id', 'followers', or 'likes'.", 400)

#         payload = {
#             "page_id": page_id,
#             "followers": followers,
#             "likes": likes
#         }

#         if recorded_at:
#             payload["recorded_at"] = recorded_at

#         response = supabase.table("influence_history").insert(payload).execute()

#         if hasattr(response, "error") and response.error:
#             return error_response(f"Failed to insert influence record: {getattr(response.error, 'message', str(response.error))}", 500)
#         if not getattr(response, "data", []):
#             return error_response("Insert succeeded but returned no data.", 204)

#         return success_response(response.data, 201)

#     except Exception as e:
#         return error_response(str(e), 500)


@data_bp.route("/get_influence_history", methods=["GET"])
def get_influence_history():
    try:
        response = supabase.table("influence_history").select("*").execute()

        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence history: {getattr(response, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found.", 404)

        return success_response(response.data, 200)

    except Exception as e:
        return error_response(str(e), 500)



@data_bp.route("/get_page_influence", methods=["GET"])
def get_page_influence():
    try:
        page_id = request.args.get("page_id")
        date_str = request.args.get('date')  
        date_obj = datetime.fromisoformat(date_str) if date_str else None
        if not page_id:
            return error_response("Missing required query param: 'page_id'.", 400)
        
        response = None
        
        if date_obj:
            date_iso = date_obj.isoformat() 
            
            response = supabase.table("influence_history").select("*").eq('page_id', page_id).gte('recorded_at', date_iso).execute()
        else:
            response = supabase.table("influence_history").select("*").eq('page_id', page_id).execute()
        


        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found for this page.", 404)

        return success_response(response.data, 200)

    except Exception as e:
        return error_response(str(e), 500)


@data_bp.route("/get_entity_influence", methods=["GET"])
def get_entity_influence():
    try:
        entity_id = request.args.get("entity_id")
        date_str = request.args.get('date')  
        date_obj = datetime.fromisoformat(date_str) if date_str else None
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)
        
        response = None
        
        if date_obj:
            date_iso = date_obj.isoformat() 
            
            response = supabase.rpc("get_entity_influence_scores", { "entity_id_input": int(entity_id) }).gte("recorded_at", date_iso).execute()
        else:
            response = supabase.rpc("get_entity_influence_scores", { "entity_id_input": int(entity_id) }).execute()
        


        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found for this entity.", 404)

        return success_response(response.data, 200)

    except Exception as e:
        return error_response(str(e), 500)




@data_bp.route("/get_ranking", methods=["GET"])
def get_ranking():
    try:    
        
        response = supabase.rpc("get_entity_platform_followers").execute()
        
        if hasattr(response, "error") and response.error:
            return error_response(f"Error fetching influence: {getattr(response.error, 'message', str(response.error))}", 500)
        if not getattr(response, "data", []):
            return error_response("No influence history found for this page.", 404)
        data = response.data

        # Step 1: Aggregate Data per Entity
        entity_map = defaultdict(lambda: {"total_followers": 0, "platforms": defaultdict(int)})

        for row in data:
            entity_id = row["entity_id"]
            entity_name = row["entity_name"]
            followers = row["total_followers"]
            platform = row["platform"]

            entity_map[entity_id]["entity_name"] = entity_name
            entity_map[entity_id]["total_followers"] += followers
            entity_map[entity_id]["platforms"][platform] += followers

        # Step 2: Convert to List and Rank Entities
        entities_list = []
        for entity_id, info in entity_map.items():
            entities_list.append({
                "entity_id": entity_id,
                "entity_name": info["entity_name"],
                "total_followers": info["total_followers"],
                "platforms": dict(info["platforms"])
            })
            
        # Step 3: Rank by Total Followers
        entities_list.sort(key=lambda x: x["total_followers"], reverse=True)
        for idx, entity in enumerate(entities_list, start=1):
            entity["rank"] = idx


        
        return success_response(entities_list, 200)

    except Exception as e:
        return error_response(str(e), 500)

