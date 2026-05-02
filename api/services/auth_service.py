# services/auth_service.py
import os
import jwt
from datetime import datetime, timedelta, timezone
from api.models.user_model import User
from api.repositories.page_repository import PageRepository
from api.repositories.user_repository import UserRepository
from api.utils.logging_utils import instrument_service_class
from api.utils.page_uuid import create_page_uuid, normalize_page_link


SECRET_KEY = os.environ.get("SECRET_KEY")
ALLOWED_PAGE_PLATFORMS = {"facebook", "instagram", "x", "tiktok", "linkedin", "youtube"}


@instrument_service_class
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

    @staticmethod
    def issue_token_pair(user, access_delta=timedelta(days=1), refresh_delta=timedelta(days=30)):
        access_token_exp = datetime.now(timezone.utc) + access_delta
        access_payload = {
            "user_id": user.id,
            "role": user.role,
            "exp": access_token_exp,
        }
        access_token = jwt.encode(access_payload, SECRET_KEY, algorithm="HS256")

        refresh_token_exp = datetime.now(timezone.utc) + refresh_delta
        refresh_payload = {
            "user_id": user.id,
            "exp": refresh_token_exp,
        }
        refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_token_exp": access_token_exp,
            "refresh_token_exp": refresh_token_exp,
        }

    @staticmethod
    def persist_refresh_token(user_id, token, exp):
        UserRepository.update_refresh_token(user_id, token=token, exp=exp)

    @staticmethod
    def build_auth_response(user, access_token, refresh_token):
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_role": user.role,
            "user_id": user.id,
        }

    @staticmethod
    def create_page_uuid(link):
        return create_page_uuid(link)

    @staticmethod
    def create_entity_pages(entity, pages_data, commit=True):
        pages_response = []
        if isinstance(pages_data, list) and len(pages_data) > 0:
            for page in pages_data:
                if not isinstance(page, dict) or "platform" not in page or "link" not in page:
                    raise ValueError("Invalid page data, platform and link are required for every page")

                platform = str(page["platform"]).strip()
                link = normalize_page_link(page["link"])
                if not platform or not link:
                    raise ValueError("Invalid page data, platform and link must be non-empty")

                normalized_platform = platform.lower()
                if normalized_platform not in ALLOWED_PAGE_PLATFORMS:
                    raise ValueError(
                        f"Invalid page platform '{platform}'. Allowed platforms are: {sorted(ALLOWED_PAGE_PLATFORMS)}"
                    )

                page_uuid = AuthService.create_page_uuid(link)
                created_page = PageRepository.create(
                    uuid=page_uuid,
                    name=entity.name,
                    platform=normalized_platform,
                    link=link,
                    entity_id=entity.id,
                    commit=commit,
                )

                pages_response.append(
                    {
                        "page_id": created_page.uuid,
                        "page_link": created_page.link,
                        "platform": created_page.platform,
                    }
                )

        return pages_response if len(pages_response) > 0 else None
