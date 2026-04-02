# services/auth_service.py
import os
import jwt
from datetime import datetime, timedelta, timezone
from api.models.user_model import User
from api.repositories.user_repository import UserRepository


SECRET_KEY = os.environ.get("SECRET_KEY")

class AuthService:
    @staticmethod
    def signup(first_name, email, password, role="registered", last_name="", phone_number=None, profession="other", is_verified=True):
        if UserRepository.find_by_email(email):
            raise ValueError("Email already exists")
        
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            phone_number=phone_number,
            profession=profession,
            is_verified=is_verified
        )

        user.set_password(password)  
        UserRepository.save_user(user)

        return user

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
