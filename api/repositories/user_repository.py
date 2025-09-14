# repositories/user_repo.py
from datetime import datetime
from api.models.user_model import User
from api import db

class UserRepository:
    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        return User.query.get(user_id)
    
    @staticmethod
    def find_by_email(email):
        return User.query.filter_by(email=email).first()
    
    @staticmethod
    def create_user(first_name, last_name, email, password, role="public"):
        user = User(first_name=first_name, last_name=last_name, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def update_refresh_token(user_id: int, token: str, exp: datetime) -> None:
       
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        user.refresh_token = token
        user.refresh_token_exp = exp
        db.session.commit()
