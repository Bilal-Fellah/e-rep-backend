from collections import defaultdict, OrderedDict
from datetime import datetime, date, timedelta
import os
import jwt
from api.repositories.page_history_repository import PageHistoryRepository
from flask import request
from api.routes.main import error_response, success_response
from api.utils.posts_utils import _to_number, ensure_datetime
from . import data_bp
from sqlalchemy.exc import SQLAlchemyError
from api.utils.data_keys import platform_metrics, summarize_days
from api.utils.interaction_stats import  fill_missing_scores
import traceback


SECRET = os.environ.get("SECRET_KEY")


@data_bp.route("/get_after_time", methods=["GET"])
def get_after_time():
    allowed_roles = ["admin"]

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
        history_list = PageHistoryRepository().get_platform_history(platform=platform)
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
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
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
    # try:
    #     token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    #     payload = jwt.decode(token, SECRET, algorithms=['HS256'])

    # except Exception:
    #     pass
    
    try:

        data = PageHistoryRepository.get_all_entities_ranking()


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
    # get only last week interactions
    start_date = datetime.now() - timedelta(days=7)

    # get all entities posts
    data = PageHistoryRepository.get_all_entities_posts(date_limit=start_date)

    
    structured_entities = defaultdict(lambda: {
        "platforms": {},
        "posts": []
    })

    for row in data:
        entity = structured_entities[row.entity_id]

        # static entity-level fields
        entity["entity_id"] = row.entity_id
        entity["entity_name"] = row.entity_name
        entity["category"] = row.category
        entity["root_category"] = row.root_category

        # platform-level aggregation
        entity["platforms"][row.platform] = {
            "followers": row.raw_followers or 0,
            "page_id": row.page_id,
            "page_name": row.page_name,
            "profile_url": row.page_url,
            "profile_image_url": row.profile_url,
        }

        # keep posts metrics for scoring
        if row.posts_metrics:
            entity["posts"].append({
                "platform": row.platform,
                "metrics": row.posts_metrics
            })

    
    entity_scores = []

    for entity_id, entity_data in structured_entities.items():
        total_score = 0
        total_posts = 0

        for post_block in entity_data["posts"]:
            platform = post_block["platform"]
            posts_metrics = post_block["metrics"]

            if platform not in platform_metrics:
                continue

            metrics_def = platform_metrics[platform]["metrics"]

            for post in posts_metrics:
                for m in metrics_def:
                    value = post.get(m["name"], 0) or 0
                    total_score += value * m["score"]
                total_posts += 1

        total_followers = sum(
            p["followers"] for p in entity_data["platforms"].values()
        )

        entity_scores.append({
            "entity_id": entity_id,
            "entity_name": entity_data["entity_name"],
            "category": entity_data["category"],
            "root_category": entity_data["root_category"],
            "platforms": entity_data["platforms"],
            "total_score": total_score,
            "average_score": total_score / total_posts if total_posts else 0,
            "total_followers": total_followers
        })

    entity_scores.sort(key=lambda x: x["total_followers"], reverse=True)

    for idx, entity in enumerate(entity_scores, start=1):
        entity["rank"] = idx

    return success_response(entity_scores, 200)


@data_bp.route("/get_entity_interaction_stats", methods=["GET"])
def get_entity_interaction_stats():
    try:
        entity_id = request.args.get("entity_id", type=int)
        start_date = request.args.get("start_date")
        if start_date:
            start_date = ensure_datetime(start_date)

        data = PageHistoryRepository.get_entity_posts__old(entity_id=entity_id)
        if not data:
            return error_response(f"No data found for entity {entity_id}.", 404)

        # --- STEP 1: Structure raw rows by day ---
        # days = { "2024-12-01": { post_id: post_dict, ... } }
        daily_posts = {}

        for row in data:
            platform = row.platform if hasattr(row, "platform") else row[2]
            posts = row.posts if hasattr(row, "posts") else row[4]
            recorded_at = row.recorded_at if hasattr(row, "recorded_at") else row[3]

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

            for post in posts:
                if not isinstance(post, dict):
                    continue

                post_id = post.get(id_key)
                if not post_id:
                    continue

                post_date = post.get(date_key)
                if start_date and post_date and ensure_datetime(post_date) < start_date:
                    continue

                # Build compact metrics dict
                daily_posts[day_key][post_id] = {
                    "post_id": post_id,
                    "platform": platform,
                    "create_time": post_date,
                    **{m["name"]: post.get(m["name"], 0) for m in metrics}
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
        
        
        summary = summarize_days(final_output, platform_metrics)
        summary = fill_missing_scores(summary)


        return success_response(summary, 200)

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
        
        data = []
        for id in entity_ids:
            data.extend(PageHistoryRepository.get_entity_posts(entity_id=id))

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(f"No data found for entity {entity_ids}.", 404)

        post_scores = []

        for row in data:
            # row: [page_id, page_name, platform, recorded_at, posts, entity_id]
            platform = row[2]
            page_id = row[0]

            if platform not in platform_metrics:
                continue

            posts = row.posts
            if isinstance(posts, list) and len(posts) > 0:
                posts = posts[0]  
            else:
                continue

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]

            for post in posts:
                post_sc = 0

                post_date = post.get(platform_metrics[platform]['date'])
                if start_date and start_date > ensure_datetime(post_date):
                    continue # skip older posts

                # calculate score
                for m in metrics:
                    metric_name = m["name"]
                    metric_score = m["score"]

                    value = post.get(metric_name, 0)
                    post_sc += value * metric_score

                post_scores.append(
                    {
                        "post_id": post.get(id_key),
                        **{m["name"]: post.get(m["name"], 0) for m in metrics},
                        "score": post_sc,
                        "platform": platform,
                        "create_time": post.get(platform_metrics[platform]['date']),
                        "page_id": page_id,
                        "entity_id": row[5]
                    }
                )

        return success_response(post_scores, 200)

    except Exception as e:
        traceback.print_exc()
        return error_response(f"Internal server error: {str(e)}", 500)
