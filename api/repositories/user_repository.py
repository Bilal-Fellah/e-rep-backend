# repositories/user_repo.py
from api.models.user_model import User
from api import db

class UserRepository:
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
