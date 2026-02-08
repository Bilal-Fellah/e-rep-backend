# services/auth_service.py
import jwt
from datetime import datetime, timedelta, timezone
from api.repositories.user_repository import UserRepository
from api import app
from werkzeug.security import generate_password_hash


SECRET_KEY = app.config["SECRET_KEY"]

class AuthService:
    @staticmethod
    def signup(first_name, email, password, role="registered", last_name="", phone_number=None):
        if UserRepository.find_by_email(email):
            raise ValueError("Email already exists")
        
        hashed_password = generate_password_hash(password)

        return UserRepository.create_user(first_name, last_name, email, hashed_password, role)

    @staticmethod
    def login(email, password):
        user = UserRepository.find_by_email(email)
        if not user or not user.check_password(password):
            raise ValueError("Invalid credentials")

        payload = {
            "user_id": user.id,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return token
