# routes/auth_routes.py
import json
import json
from api.utils.auth import validate_email
from flask import Blueprint, request, jsonify
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_repository import PageRepository
from api.repositories.user_repository import UserRepository
import jwt
from datetime import datetime, timedelta, timezone
import os
import uuid
from api.utils.auth import MAILS_FILE

from api.routes.main import error_response, success_response
# from app import app
SECRET = os.environ.get("SECRET_KEY")
auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register_mail", methods=["POST"])
def register_mail():
    try:
        email = request.json.get("email")
        if not email or not validate_email(email):
            return error_response("Invalid email", 400)
        
        if UserRepository.find_by_email(email):
            return error_response("Email already exists", 400)
        
        init_status = "unverified"
        email_object = {
            "email": email,
            "status": init_status,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }
        with open(MAILS_FILE, "r+") as f:
            mails = json.load(f)

            mails.append(email_object)
            f.seek(0)
            json.dump(mails, f, indent=4)
            
        return success_response(data={"message": f"Email {email} registered for temporary access"})
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route("/register_user", methods=["POST"])
def register_user():
    try:
        data = request.json
        required_keys = ['first_name','last_name','email','password']
        for key in required_keys:
            if key not in data:
                return error_response(f"missing required key: {key}", 400)

        allowed_roles = ["public","registered","anonymous","subscribed","admin"]
        if data.get('role', 'registered') not in allowed_roles:
            return error_response(f"role must be in {allowed_roles}")
        
        if UserRepository.find_by_email(data["email"]):
            return jsonify({"error": "Email already exists"}), 400
        
        user = UserRepository.create_user(
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            password=data["password"],
            role= data.get('role', 'registered')
        )

        # Access token (1 day)
        access_token_exp = datetime.now(timezone.utc) + timedelta(days=1)
        access_payload = {
            "user_id": user.id,
            "role": user.role,
            "exp": access_token_exp
        }
        access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")
        
        # Refresh token (30 days)
        refresh_token_exp = datetime.now(timezone.utc) + timedelta(days=30)
        refresh_payload = {
            "user_id": user.id,
            "exp": refresh_token_exp
        }
        refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

        # Save refresh token & expiry in DB
        UserRepository.update_refresh_token(
            user.id,
            token=refresh_token,
            exp=refresh_token_exp
        )

        response = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_role": user.role,
            "user_id": user.id
        }

        return success_response(data=response )
    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route("/register_entity", methods=["POST"])
def register_entity():
    allowed_roles = ["admin"]

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        if not payload:
            return error_response("No valid token has been sent", 401)
        role = payload['role']
        if role not in allowed_roles:
            return error_response("Access denied", 403)
        
        required_keys = ["entity_name","type", "category_id"]
        data = request.json
        
        for key in required_keys:
            if key not in data:
                return error_response("Missing required parameters", 400)
            
        name = data["entity_name"]
        entity_type = data["type"]
        category_id = data["category_id"]

        if not CategoryRepository.get_by_id(category_id= category_id):
            return error_response("wrong category_id", 400)

        if EntityRepository.get_by_name(entity_name= name):
            return error_response(f"entity name {name} already exists")

        # add the entity
        entity = EntityRepository.create(
            name=name,
            type_=entity_type
        )

        if not entity:
            return error_response("failed to insert entity data", 500)
        entity_category = EntityCategoryRepository.add(entity_id=entity.id, category_id=category_id)

        if not entity_category:
            return error_response("failed to map entity to category", 500)

        pages_data = None
        if 'pages' in data:
            pages_data = data['pages']
        
        pages_response = []
        if isinstance(pages_data, list) and len(pages_data) > 0:
            # insert pages as well
            for page in pages_data:
                if 'platform' not in page or 'link' not in page:
                    return error_response(f"Invalid page data, platform and link are required for every page")
                platform = page['platform']
                link = page['link']

                new_uuid = uuid.uuid5(uuid.NAMESPACE_URL, platform + link)

                page = PageRepository.create(
                    uuid=new_uuid, 
                    name=entity.name,
                    platform=platform,
                    link=link,
                    entity_id=entity.id
                )
                pages_response.append({"page_id": page.uuid, "page_link": page.link, "platform": page.platform})
        pages_response = pages_response if len(pages_response)>0 else None
        payload = {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "category_id": entity_category.category_id,
                    "pages": pages_response 
                }
        
        return success_response(payload, status_code=201)
    
    except jwt.ExpiredSignatureError:
        return error_response("Token has expired", 401)
    except jwt.InvalidTokenError:
        return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)




@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        user = UserRepository.find_by_email(data["email"])
        if not user or not user.check_password(data["password"]):
            return error_response("Invalid credentials", status_code=401)
        
        access_token_exp = datetime.now(timezone.utc) + timedelta(days=1)
        # Access token (2 hours)
        access_payload = {
            "user_id": user.id,
            "role": user.role,
            "exp": access_token_exp
        }
        access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")
        
        refresh_token_exp = datetime.now(timezone.utc) + timedelta(days=30)
        # Refresh token (30 days)
        refresh_payload = {
            "user_id": user.id,
            "exp": refresh_token_exp
        }
        refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

        # Save refresh token & expiry in DB
        UserRepository.update_refresh_token(
            user.id,
            token=refresh_token,
            exp=refresh_token_exp
        )

        response = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_role": user.role,
            "user_id": user.id
        }

        return success_response(response,status_code=200)
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route("/get_user_data", methods=["POST"])
def get_user_data():
    
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # Example: fetch the user from DB if needed
        user = UserRepository.get_by_id(payload["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 404

        return success_response(data={
            "email": user.email,
            "user_id": user.id,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": user.created_at,
        })
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route("/refresh_token", methods=["POST"])
def refresh():

    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Missing refresh token"}), 400
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = UserRepository.get_by_id(payload["user_id"])

        if not user or user.refresh_token != token:
            return jsonify({"error": "Invalid refresh token"}), 401
        if user.refresh_token_exp < datetime.now(timezone.utc):
            return jsonify({"error": "Refresh token expired"}), 401

        # New 2-hour access token
        new_access = jwt.encode({
            "user_id": user.id,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=2)
        }, SECRET, algorithm="HS256")
        response = {
            "access_token": new_access
        }
        return success_response(response)
    except jwt.InvalidTokenError:
        return error_response("Invalid refresh token", status_code=401)


@auth_bp.route("/validate_user_role", methods=["POST"])
def validate_user_role():
    allowed_roles = ["admin"]
    required_keys = ["user_id", "role"]
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # Example: fetch the user from DB if needed
        user = UserRepository.get_by_id(payload["user_id"])
        if not user:
            return error_response("User not found", 404)
        role = user.role
        if role not in allowed_roles:
            return error_response("Access denied", 403)

        data = request.get_json()
        for key in required_keys:
            if key not in data:
                return error_response(f"Missing required key {key}", 400)

        user_id = data['user_id']
        role = data['role']

        user = UserRepository.update_role(user_id=user_id, role= role)
        response = {"user_id": user.id, 'role': user.role}
        return success_response(data=response)

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route("/test_oauth", methods=["POST"])
def test_oauth():
    return success_response(data={"message": "OAuth redirected here!"})