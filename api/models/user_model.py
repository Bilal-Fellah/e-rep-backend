# models/user.py
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from api import db

class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum("public","registered","subscribed","admin", name="user_roles"), default="public")
    
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    refresh_token = db.Column(db.Text)
    refresh_token_exp = db.Column(db.DateTime)

    phone_number = db.Column(db.String(20), unique=True, nullable=True)


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
