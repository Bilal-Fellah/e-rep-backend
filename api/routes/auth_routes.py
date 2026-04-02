# routes/auth_routes.py
import email
import json
import json
from api.services.auth_service import AuthService
from api.utils.auth import validate_email, _extract_token
from flask import Blueprint, request, jsonify, redirect, make_response
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_repository import PageRepository
from api.repositories.user_repository import UserRepository
import jwt
from datetime import datetime, timedelta, timezone
import os
import uuid
from api.utils.auth import MAILS_FILE, ENTITIES_FILE
from api.utils.validators import (
    validate_required_keys, validate_enum, sanitize_string,
    validate_email as v_email, validate_phone, validate_password,
    ALLOWED_ROLES, ALLOWED_PROFESSIONS
)

from api.routes.main import error_response, success_response
# from app import app
SECRET = os.environ.get("SECRET_KEY")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL", "https://app.brendex.net")
FRONTEND_COOKIE_DOMAIN = os.environ.get("FRONTEND_COOKIE_DOMAIN", ".brendex.net")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
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
        required_keys = ['full_name','email', 'password', 'phone_number', 'profession']
        missing = validate_required_keys(data, required_keys)
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not v_email(data['email']):
            return error_response("Invalid email format", 400)

        if not validate_password(data['password']):
            return error_response("Password must be at least 8 characters", 400)
        
        if not validate_phone(data['phone_number']):
            return error_response("Invalid phone number format", 400)

        role = data.get('role', 'registered')
        err = validate_enum(role, ALLOWED_ROLES, 'role')
        if err:
            return error_response(err, 400)
        
        err = validate_enum(data['profession'], ALLOWED_PROFESSIONS, 'profession')
        if err:
            return error_response(err, 400)

        full_name = sanitize_string(data['full_name'], 100)
        if not full_name:
            return error_response("Invalid full_name", 400)
        
        user = AuthService.signup(
            first_name=full_name.split()[0],
            last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else "",
            email=data["email"].strip().lower(),
            password=data["password"],
            phone_number=data["phone_number"].strip(),
            role=role,
            profession=data['profession'],
            is_verified=True
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


@auth_bp.route("/register_entity_name", methods=["POST"])
def register_entity_name():
    allowed_roles = ["admin", "registered", "subscribed"]
    try:
        entity_name = request.json.get("entity_name")

        if EntityRepository.get_by_name(entity_name= entity_name):
            return error_response(f"entity name {entity_name} already exists")
        
        
        init_status = "unverified"
        entity_object = {
            "entity_name": entity_name,
            "status": init_status,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(ENTITIES_FILE, "r+") as f:
            entities = json.load(f)

            entities.append(entity_object)
            f.seek(0)
            json.dump(entities, f, indent=4)
            
        return success_response(data={"message": f"Entity {entity_name} registered for temporary access"})
    except Exception as e:
        return error_response(str(e), 500)



@auth_bp.route("/register_entity", methods=["POST"])
def register_entity():
    allowed_roles = ["admin", "registered", "subscribed"]

    try:
        token = _extract_token("access_token")
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
        missing = validate_required_keys(data, ['email', 'password'])
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not v_email(data['email']):
            return error_response("Invalid email format", 400)

        user = UserRepository.find_by_email(data["email"].strip().lower())
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
        token = _extract_token("access_token")
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # Example: fetch the user from DB if needed
        user = UserRepository.get_by_id(payload["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 404

        return success_response(data={
            "email": user.email,
            "user_id": user.id,
            "role": user.role,
            "profession": user.profession,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
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
        token = _extract_token("refresh_token")
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
        flask_response = make_response(success_response(response))
        flask_response.set_cookie(
            "access_token",
            new_access,
            expires=datetime.now(timezone.utc) + timedelta(hours=2),
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="None",
            domain=FRONTEND_COOKIE_DOMAIN or None,
            path="/"
        )
        return flask_response
    except jwt.InvalidTokenError:
        return error_response("Invalid refresh token", status_code=401)


@auth_bp.route("/validate_user_role", methods=["POST"])
def validate_user_role():

    """ this route updates the user role, after signing from google auth"""


    allowed_roles = ["admin", "registered", "subscribed"]
    required_keys = ["user_id", "role"]
    try:
        token = _extract_token("access_token")
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

        user = UserRepository.update_role(user_id=user_id, role= role, is_verified=True)
        response = {"user_id": user.id, 'role': user.role}
        return success_response(data=response)

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return error_response(str(e), 500)


@auth_bp.route("/complete_profile", methods=["POST"])
def complete_profile():
    """
    After Google sign-up, allows the user to add phone_number and profession.
    Requires a valid access token.
    """
    try:
        token = _extract_token("access_token")
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = UserRepository.get_by_id(payload["user_id"])
        if not user:
            return error_response("User not found", 404)

        data = request.json
        missing = validate_required_keys(data, ["phone_number", "profession"])
        if missing:
            return error_response(f"missing required key: {missing}", 400)

        if not validate_phone(data["phone_number"]):
            return error_response("Invalid phone number format", 400)

        err = validate_enum(data["profession"], ALLOWED_PROFESSIONS, "profession")
        if err:
            return error_response(err, 400)

        user = UserRepository.update_profile(
            user_id=user.id,
            phone_number=data["phone_number"].strip(),
            profession=data["profession"]
        )

        return success_response(data={
            "user_id": user.id,
            "phone_number": user.phone_number,
            "profession": user.profession,
        })

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route("/redirect_to_app", methods=["POST"])
def redirect_to_app():

    """ This route is called after user finishes subscription, and now to be redirected to the app with a valid tokens
        It receives the email as input, checks if the user exists and is subscribed, then generates access and refresh tokens 
        and redirects the user to the app subdomain after setting those tokens in cookies
    """

    allowed_roles = ['admin', 'registered', 'subscribed']

    try:

        token = _extract_token("access_token")
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])

        user_id = payload['user_id']
        user = UserRepository.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # now we verify if the user has permitted role
        user_role = payload["role"]
        if user_role not in allowed_roles:
            return error_response("User role doesnt has enough privilege", 401)
        
        # now we save the cookies into the new website
        access_token_exp = datetime.now(timezone.utc) + timedelta(days=1)
        access_payload = {  
            "user_id": user.id,
            "role": user.role,
            "exp": access_token_exp 
        }
        access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")    
        refresh_token_exp = datetime.now(timezone.utc) + timedelta(days=30)
        refresh_payload = {
            "user_id": user.id,
            "exp": refresh_token_exp   
        }       
        refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

        UserRepository.update_refresh_token(
            user.id,
            token=refresh_token,
            exp=refresh_token_exp
        )

        cookie_domain = FRONTEND_COOKIE_DOMAIN or None
        response = make_response(redirect(FRONTEND_REDIRECT_URL))
        response.set_cookie(
            "access_token",
            access_token,
            expires=access_token_exp,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="None",
            domain=cookie_domain,
            path="/"
        )
        response.set_cookie(
            "refresh_token",
            refresh_token,
            expires=refresh_token_exp,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="None",
            domain=cookie_domain,
            path="/"
        )

        return response

        

    except Exception as e:
        return error_response(str(e), 500)
