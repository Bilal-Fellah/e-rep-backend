# routes/auth_routes.py
from flask import Blueprint, request, jsonify
from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.user_repository import UserRepository
import jwt
from datetime import datetime, timedelta
import os

from api.routes.main import error_response, success_response
# from app import app
SECRET = os.environ.get("SECRET_KEY")
auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    if UserRepository.find_by_email(data["email"]):
        return jsonify({"error": "Email already exists"}), 400
    
    user = UserRepository.create_user(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        password=data["password"],
        role=data.get("role", "public")
    )
    return jsonify({"message": "User created", "id": user.id}), 201


@auth_bp.route("/register_entity", methods=["POST"])
def register_entity():
    required_keys = ["entity_name","type", "category_id"]
    data = request.json
    
    for key in required_keys:
        if key not in data:
            return error_response("missing required keys", 400)
        
    name = data["entity_name"]
    entity_type = data["type"]
    category_id = data["category_id"]

    if not CategoryRepository.get_by_id(category_id= category_id):
        return error_response("wrong category_id")

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

    payload = {
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "category_id": entity_category.category_id
            }
    
    return success_response(payload, status_code=201)




@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    user = UserRepository.find_by_email(data["email"])
    if not user or not user.check_password(data["password"]):
        return error_response("Invalid credentials", status_code=401)

    # Access token (2 hours)
    access_payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }
    access_token = jwt.encode(access_payload, SECRET, algorithm="HS256")

    # Refresh token (7 days)
    refresh_payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    refresh_token = jwt.encode(refresh_payload, SECRET, algorithm="HS256")

    # Save refresh token & expiry in DB
    UserRepository.update_refresh_token(
        user.id,
        token=refresh_token,
        exp=datetime.utcnow() + timedelta(days=7)
    )

    response = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_role": user.role,
        "user_id": user.id
    }

    return success_response(response,status_code=200)

@auth_bp.route("/get_user_data", methods=["POST"])
def get_user_data():
   
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    try:
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
    

@auth_bp.route("/refresh_token", methods=["POST"])
def refresh():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return jsonify({"error": "Missing refresh token"}), 400

    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = UserRepository.get_by_id(payload["user_id"])
        if not user or user.refresh_token != token:
            return jsonify({"error": "Invalid refresh token"}), 401
        if user.refresh_token_exp < datetime.utcnow():
            return jsonify({"error": "Refresh token expired"}), 401

        # New 2-hour access token
        new_access = jwt.encode({
            "user_id": user.id,
            "role": user.role,
            "exp": datetime.utcnow() + timedelta(hours=2)
        }, SECRET, algorithm="HS256")
        response = {
            "access_token": new_access
        }
        return success_response(response)
    except jwt.InvalidTokenError:
        return error_response("Invalid refresh token", status_code=401)

