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
    role = db.Column(db.Enum("registered","subscribed","admin", name="user_roles"), default="registered", nullable=False)
    profession = db.Column(db.Enum("community_manager","marketing","ceo","journalist","influencer","student","sales","other", name="user_professions"), nullable=True, default="other")
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    refresh_token = db.Column(db.Text)
    refresh_token_exp = db.Column(db.DateTime)

    phone_number = db.Column(db.String(20), unique=True, nullable=True)

    is_verified = db.Column(db.Boolean, default=False)
    
    # Marker for accounts with no usable password (e.g. Google OAuth users).
    # No value produced by generate_password_hash() equals this, and
    # check_password() refuses it outright, so such accounts can never log in
    # via the password endpoint.
    UNUSABLE_PASSWORD = "!"

    def set_password(self, password):
        # Never hash an empty password — generate_password_hash("") is a VALID
        # hash of the empty string, which would let anyone log in with "".
        if not password:
            self.password_hash = self.UNUSABLE_PASSWORD
            return
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if (
            not password
            or not self.password_hash
            or self.password_hash == self.UNUSABLE_PASSWORD
        ):
            return False
        return check_password_hash(self.password_hash, password)
