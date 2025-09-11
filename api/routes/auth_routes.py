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
        return jsonify({"error": "Invalid credentials"}), 401

    payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")

    return jsonify({"token": token, "role": user.role})
