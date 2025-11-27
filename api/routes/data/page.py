from flask import request
import jwt
from api.repositories.page_history_repository import PageHistoryRepository
from api.routes.main import error_response, success_response
from api.repositories.page_repository import PageRepository
from api.utils.data_keys import platform_metrics
import uuid

from api.utils.posts_utils import ensure_datetime
from . import data_bp
import os

SECRET = os.environ.get("SECRET_KEY")

@data_bp.route("/add_page", methods=["POST"])
def add_page():
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
        platform = data.get("platform", "").strip().lower()
        link = data.get("link", "").strip().lower()
        entity_id = data.get("entity_id")

        if not platform or not link or not entity_id:
            return error_response("Missing required fields: 'platform', 'link', or 'entity_id'.", status_code=400)

        # Generate the UUID by hashing the platform and link
        new_uuid = uuid.uuid5(uuid.NAMESPACE_URL, platform + link)

        page = PageRepository.create(
            uuid=new_uuid, 
            name=data.get("name", "").strip() or link,
            platform=platform,
            link=link,
            entity_id=entity_id
        )

        return success_response({
            "uuid": str(page.uuid),  # Convert the UUID object to a string for the response
            "name": page.name,
            "link": page.link,
            "platform": page.platform,
            "entity_id": page.entity_id
        }, status_code=201)



    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), status_code=500)

@data_bp.route("/delete_page", methods=["POST"])
def delete_page():
    allowed_roles = ["admin"]

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

        deleted = PageRepository.delete(page_id)
        if not deleted:
            return error_response(f"No page found with id {page_id} or already deleted.", status_code=404)

        return success_response({"deleted_id": page_id}, status_code=200)


    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), status_code=500)


@data_bp.route("/get_all_pages", methods=["GET"])
def get_all_pages():
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)
        
        pages = PageRepository.get_all()
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


    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), status_code=500)

@data_bp.route("/get_pages_by_platform", methods=["GET"])
def get_pages_by_platform():
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
        pages = PageRepository.get_by_platform(platform)
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


    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), status_code=500)

@data_bp.route("/get_page_interaction_stats", methods=["GET"])
def get_page_interaction_stats():
    try:
        page_id = request.args.get("page_id")
        start_date = request.args.get("start_date")
        if start_date:
            start_date = ensure_datetime(start_date)
        else:
            start_date = None

        data = PageHistoryRepository.get_page_posts(page_id=page_id)

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(f"No data found for page {page_id}.", 404)

        post_scores = []

        for row in data:
            # row: [page_id, page_name, platform, recorded_at, posts_list]
            platform = row[2]

            if platform not in platform_metrics:
                continue

            posts = row[4]
            if isinstance(posts, list) and len(posts) > 0:
                posts = posts[0]  # your format: [[{post1}, {post2}, ...]]
            else:
                continue

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]

            for post in posts:
                post_sc = 0

                # check date
                
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
                        "create_time": post.get(platform_metrics[platform]['date'])
                    }
                )

        return success_response(post_scores, 200)

    except Exception as e:
        return error_response(f"Internal server error: {str(e)}", 500)
