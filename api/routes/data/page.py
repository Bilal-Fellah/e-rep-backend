from flask import request
import jwt
from api.routes.main import error_response, success_response
from api.repositories.page_repository import PageRepository
import uuid
from . import data_bp
import os

SECRET = os.environ.get("SECRET_KEY")

# ... other imports

@data_bp.route("/add_page", methods=["POST"])
def add_page():
    allowed_roles = ["admin", "subscribed", "registered"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
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
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
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
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
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
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
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
