# services/auth_service.py
import jwt
from datetime import datetime, timedelta
from api.repositories.user_repository import UserRepository
from api import app

SECRET_KEY = app.config["SECRET_KEY"]

class AuthService:
    @staticmethod
    def signup(first_name, last_name, email, password, role="public"):
        if UserRepository.find_by_email(email):
            raise ValueError("Email already exists")
        
        return UserRepository.create_user(first_name, last_name, email, password, role)

    @staticmethod
    def login(email, password):
        user = UserRepository.find_by_email(email)
        if not user or not user.check_password(password):
            raise ValueError("Invalid credentials")

        payload = {
            "user_id": user.id,
            "role": user.role,
            "exp": datetime.utcnow() + timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return token
