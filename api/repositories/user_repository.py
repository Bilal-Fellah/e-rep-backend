# Data-access methods for user repository.
# repositories/user_repo.py
from datetime import datetime, timezone
from sqlalchemy import or_
from api.models.user_model import User
from api import db
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class UserRepository:
    @staticmethod
    def _search_query(search: str | None, role: str | None = None):
        query = User.query
        term = (search or "").strip().lower()
        if term:
            like = f"%{term}%"
            query = query.filter(
                or_(
                    db.func.lower(User.email).like(like),
                    db.func.lower(User.first_name).like(like),
                    db.func.lower(User.last_name).like(like),
                )
            )
        if role:
            query = query.filter(User.role == role)
        return query

    @staticmethod
    def list_users(
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        role: str | None = None,
    ) -> list[User]:
        return (
            UserRepository._search_query(search, role)
            .order_by(User.created_at.desc().nullslast(), User.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def count_users(search: str | None = None, role: str | None = None) -> int:
        return UserRepository._search_query(search, role).count()

    @staticmethod
    def count_unverified() -> int:
        # is_verified is nullable; treat NULL as "not activated" too.
        return User.query.filter(User.is_verified.isnot(True)).count()

    @staticmethod
    def list_unverified(limit: int = 10) -> list[User]:
        return (
            User.query.filter(User.is_verified.isnot(True))
            .order_by(User.created_at.desc().nullslast(), User.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete(user_id: int) -> bool:
        user = db.session.get(User, user_id)
        if not user:
            return False
        db.session.delete(user)
        db.session.commit()
        return True

    @staticmethod
    def get_by_id(user_id: int) -> User | None:
        return User.query.get(user_id)
    
    @staticmethod
    def find_by_email(email):
        return User.query.filter_by(email=email).first()
    
    @staticmethod
    def create_user(first_name, last_name, email, password, role="registered", is_verified=False):
        user = User(first_name=first_name, last_name=last_name, email=email, role=role, is_verified=is_verified)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def save_user(user: User):
        
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def update_refresh_token(user_id: int, token: str, exp: datetime) -> None:

        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        user.refresh_token = token
        # `refresh_token_exp` is TIMESTAMP WITHOUT TIME ZONE, so an aware value
        # written straight through is converted using the Postgres session's
        # TimeZone — on a non-UTC server the column would silently hold local
        # wall-clock, and the reader (refresh(), which reattaches UTC) would
        # shift the whole refresh window by that offset. Convert here so what
        # lands in the column is always UTC, whatever the server is set to.
        #
        # The naive type is what the model declares (`db.Column(db.DateTime)`)
        # and is corroborated by the aware/naive TypeError that refresh() used
        # to raise on read — but no migration creates these columns, so the
        # live table was built out-of-band. If `\d users` ever shows
        # `timestamp with time zone` here, this conversion is backwards and
        # should be dropped (the reader already handles aware values).
        if exp is not None and exp.tzinfo is not None:
            exp = exp.astimezone(timezone.utc).replace(tzinfo=None)
        user.refresh_token_exp = exp
        db.session.commit()

        
    @staticmethod
    def update_role(user_id: int, role: str, is_verified: bool = True) -> User:
       
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        user.role = role
        user.is_verified = is_verified
        db.session.commit()
        return user

    @staticmethod
    def update_profession(user_id: int, profession: str) -> User:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        user.profession = profession
        db.session.commit()
        return user

    @staticmethod
    def update_profile(user_id: int, **fields) -> User:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        for key, value in fields.items():
            if hasattr(user, key):
                setattr(user, key, value)

        db.session.commit()
        return user


