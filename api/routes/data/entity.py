import ast
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import os
from api.repositories.page_repository import PageRepository
from api.utils.data_keys import platform_metrics
import jwt
from api.repositories.page_history_repository import PageHistoryRepository
from flask import request, jsonify
from api.routes.main import error_response, success_response
from api.repositories.entity_repository import EntityRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from sqlalchemy.exc import SQLAlchemyError

from api.utils.posts_utils import _to_number, ensure_datetime, parse_relative_time

from . import data_bp

import json

SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_entity", methods=["POST"])
def add_entity():
    allowed_roles = ['admin', 'subscribed', 'registered']
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

        # Insert entity
        entity = EntityRepository.create(name=name, type_=entity_type)

        # Link entity to category
        entity_category = EntityCategoryRepository.add(entity_id=entity.id, category_id=category_id)

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
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/get_all_entities", methods=["GET"])
def get_all_entities():
    allowed_roles = ["admin", "subscribed", "registered"]
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entities = EntityRepository.get_all()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
        ]
        return success_response(data, 200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/get_data_existing_entities", methods=["GET"])
def get_data_existing_entities():
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entities = EntityRepository.get_who_has_history()
        if not entities:
            return error_response("No entities found.", status_code=404)

        data = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
        ]
        return success_response(data, 200)

    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/delete_entity", methods=["POST"])
def delete_entity():
    allowed_roles = ["admin"]

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

        # Delete entity-category relations
        EntityCategoryRepository.delete_by_entity(entity_id)

        # Delete entity
        deleted = EntityRepository.delete(entity_id)
        if not deleted:
            return error_response(f"No entity found with id {entity_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": entity_id}, 200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/get_entity_profile_card", methods=["GET"])
def get_entity_profile_card():
    allowed_roles = ["admin","subscribed", "registered"]
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entity_id = request.args.get("entity_id")
        data = PageHistoryRepository.get_entity_info_from_history(entity_id)
        if type(data) != dict:
            if type(data) == list and len(data) < 1:
                message = "no data found for this entity"
                return error_response(message, status_code=404) 
            
        return success_response(data, status_code=200)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", status_code=500)

@data_bp.route("/get_entity_followers_history", methods=["GET"])
def get_entity_followers_history():
    """
    Fetch all page histories for a given entity_id (all pages belonging to entity).
    Optional: filter by date (default = today).
    """
    allowed_roles = ["admin", "subscribed", "registered"]
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

        history = PageHistoryRepository().get_followers_history_by_entity(entity_id)
        if not history or (type(history) == list and len(history)<1):
            return error_response("No history found for this entity.", 404)
        
        # Handle missing or zero followers by interpolation
        data = []
        for idx, row in enumerate(history):
            followers = row.followers
            if followers is None:
                last_val = next((r.followers for r in history[:idx] if r.followers and r.followers>0), None)
                next_val = next((r.followers for r in history[idx+1:] if r.followers and r.followers>0), None)
                if last_val and next_val:
                    followers = int((last_val + next_val) / 2)
                else: 
                    followers = last_val or next_val or 0
            
            data.append({'page_id': row.page_id, 'followers': followers, 'date': row.recorded_at, "platform": row.platform})
        return success_response(data, 200)

    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
   
@data_bp.route("/get_entity_followers_comparison", methods=["GET"])
def get_entity_followers_comparison():
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        entity_id = request.args.get("entity_id")
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)
        raw_results = PageHistoryRepository.get_category_followers_competition(entity_id)

        if not raw_results or len(raw_results) < 1:
            return error_response("No data for this entity", 404)


        data = defaultdict(lambda: {"entity_id": None, "records": []})

        for idx, row in enumerate(raw_results):
            if row.entity_name:
                if data[row.entity_name]["entity_id"] is None:
                    data[row.entity_name]["entity_id"] = row.entity_id

                date = row.recorded_at.date().isoformat()
                platform = row.platform
                followers = row.followers
                mistakes = []
                # sum directly by date (all platforms included)
                if followers:
                    data[row.entity_name]["records"].append({
                        'date': date,
                        'platform': platform,
                        'followers': followers
                    }
                    )
                else:
                    mistakes.append(row.followers)
        return success_response(data, 200)
        # we get the entities or category
    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@data_bp.route("/compare_entities_followers", methods=['POST'])
def compare_entities_followers():
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        data = request.get_json()
        entity_ids = data.get("entity_ids")
        if not entity_ids:
            return error_response("Missing required query param: 'entity_ids'.", 400)

        raw_results = PageHistoryRepository.get_entites_followers_competition(entity_ids)
        if not raw_results or len(raw_results) < 1:
            return error_response("No data for this entities", 404)


        data = defaultdict(lambda: {"entity_id": None, "records": []})

        for idx, row in enumerate(raw_results):
            if row.entity_name:
                if data[row.entity_name]["entity_id"] is None:
                    data[row.entity_name]["entity_id"] = row.entity_id

                date = row.recorded_at.date().isoformat()
                platform = row.platform
                followers = row.followers
                mistakes = []
                # sum directly by date (all platforms included)
                if row.followers:
                    data[row.entity_name]["records"].append({
                        'date': date,
                        'platform': platform,
                        'followers': followers
                    }
                    )
                else:
                    mistakes.append(row.followers)
        return success_response(data, 200)
        # we get the entities or category
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)  

@data_bp.route("/get_entity_posts_timeline", methods=["GET"])
def get_entity_posts_timeline():
    allowed_roles = ["admin", "subscribed", "registered"]

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
        
        history = PageHistoryRepository().get_entity_posts_new(entity_id)

        if not history or (type(history) == list and len(history) < 1):
            return error_response("No history found for this entity.", 404)

        sorting_map = {
            "instagram": "datetime",
            "linkedin": "date",
            "tiktok": "create_date",
            "youtube": "posted_time",
            "x": None
        }

        # Convert the input date if provided
        filter_date = None
        if date_str:
            try:
                filter_date = ensure_datetime(date_str)
                # Force into UTC-aware datetime
                if filter_date.tzinfo is None:
                    filter_date = filter_date.replace(tzinfo=timezone.utc)
                else:
                    filter_date = filter_date.astimezone(timezone.utc)
            except Exception:
                return error_response("Invalid date format provided.", 400)

        all_posts = []
        for row in history:
            platform = row.platform
            page_id = row.page_id
            page_name = row.page_name
            posts_metrics = row.posts_metrics

            # posts_metrics is already a JSONB array, no need to unwrap
            if not posts_metrics or len(posts_metrics) == 0:
                continue

            for post in posts_metrics:
                raw_date = None
                if sorting_map[platform] in post:
                    raw_date = post[sorting_map[platform]] if sorting_map[platform] else None
                if not raw_date:
                    continue

                if platform == "youtube":
                    raw_date = parse_relative_time(raw_date)

                post_date = ensure_datetime(raw_date)
                post["compare_date"] = post_date
                post["platform"] = platform
                post["page_id"] = page_id
                post["page_name"] = page_name

                # Apply date filter
                if filter_date and post_date < filter_date:
                    continue

                else:
                    all_posts.append(post)
        # Sort descending by date
        all_posts.sort(key=lambda x: x["compare_date"], reverse=True)

        # Apply max_posts if provided
        if max_posts and all_posts:
            all_posts = all_posts[:max_posts]

        return success_response(all_posts, 200)


    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except SQLAlchemyError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)
    

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
            
            res = EntityRepository.change_to_scrape(entity_id, True)
            
            return success_response({"message": f"{res}", "entity_id": entity_id}, 200)
        
        except jwt.ExpiredSignatureError:
            return error_response("Token has expired", 401)
        except jwt.InvalidTokenError:
            return error_response("Invalid token", 401)
        except Exception as e:
            return error_response(f"Internal server error: {str(e)}", 500)
        
# a route that returns top k performing posts for an entity
@data_bp.route("/get_entity_top_posts", methods=["GET"])
def get_entity_top_posts():
    try:    
        entity_id = request.args.get("entity_id", type=int)
        k = request.args.get("top_posts", type=int, default=5)
        date = request.args.get("date") 
        date = ensure_datetime(date).date() if date else datetime.now(timezone.utc).date()
        date_limit = date - timedelta(days=10)


        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)
        
        data = EntityRepository.get_entity_posts_metrics(entity_id, date_limit)
        
        # now we compute their score and sort them
        # Build compact metrics dict
        skipped = 0
        posts_num = 0

        daily_posts = {}
        for post in data:
            platform = post.platform if hasattr(post, "platform") else post[2]
            posts = post.posts_metrics if hasattr(post, "posts_metrics") else post[4]
            recorded_at = post.recorded_at if hasattr(post, "recorded_at") else post[3]
            
            if platform not in platform_metrics:
                continue
            # Normalize posts
            if not posts:
                continue

            if isinstance(posts, list) and len(posts) > 0 and isinstance(posts[0], list):
                posts = sum(posts, [])
            if not isinstance(posts, list):
                continue    

            day_key = recorded_at.date().isoformat()
            if day_key not in daily_posts:
                daily_posts[day_key] = {}

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]
            date_key = platform_metrics[platform]['date']

            for p in posts:
                posts_num += 1
                if not isinstance(p, dict):
                    skipped+=1
                    continue

                post_id = p.get(id_key)
                if not post_id:
                    skipped+=1
                    continue

                post_date = p.get(date_key)
                if date_limit and post_date and ensure_datetime(post_date).date() < date_limit:
                    skipped+=1
                    continue

                # Build compact metrics dict
                daily_posts[day_key][post_id] = {
                    "post_id": post_id,
                    "platform": platform,
                    "create_time": post_date,
                    **{m["name"]: p.get(m["name"], 0) for m in metrics},
                    **p
                }
                
                
        # --- STEP 2: Compute gained metrics against previous available day ---
        sorted_days = sorted(daily_posts.keys())
        final_output = []

        for i, day in enumerate(sorted_days):
            current_day_posts = daily_posts[day] or {}  # ensure dict
            # find nearest previous day that actually has posts (not empty)
            previous_day_posts = {}
            j = i - 1
            while j >= 0:
                candidate = daily_posts.get(sorted_days[j], {})
                if candidate and candidate != {}:  # found a day with data
                    previous_day_posts = candidate
                    break
                j -= 1

            # print(len(previous_day_posts))
            day_output = {
                "day": day,
                "posts": []
            }

            for post_id, post_data in current_day_posts.items():
                platform = post_data.get("platform")
                metrics = platform_metrics.get(platform, {}).get("metrics", [])


                previous_post = previous_day_posts.get(post_id, {})

                # Calculate gains safely, coercing to numbers and defaulting to 0
                gains = {}
                if previous_post and previous_post != {}:
                    for m in metrics:
                        name = m["name"]
                        cur_val = _to_number(post_data.get(name, 0))
                        prev_val = _to_number(previous_post.get(name, 0))

                        gains[f"gained_{name}"] = cur_val - prev_val
     
                    day_output["posts"].append({
                        **post_data,
                        **gains
                    })

            final_output.append(day_output)   
        
                
        day_gains = next((item for item in final_output if item["day"] == str(date)), None)
        # sort the posts for this day by total gained metrics, using platform metrics weights
        if day_gains:
            # Calculate scores and add them to each post
            for post in day_gains["posts"]:
                score = sum(
                    post.get(f"gained_{m['name']}", 0) * m.get("weight", 1)
                    for m in platform_metrics.get(post.get("platform"), {}).get("metrics", [])
                )
                post["total_score"] = score
            
            # Sort by score
            day_gains["posts"].sort(key=lambda x: x["total_score"], reverse=True)
            
            # Add rank to each post
            for rank, post in enumerate(day_gains["posts"], start=1):
                post["rank"] = rank
            
            # Keep only top k
            day_gains["posts"] = day_gains["posts"][:k]
        
        print(f"Processed {posts_num} posts, skipped {skipped} invalid entries.")
        return success_response(day_gains, 200)
    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", 500)
