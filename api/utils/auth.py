# Shared helper functions for auth.
import re
from flask import request
    
MAILS_FILE = 'api/database/tem_mail_registeration.json'
OAUTH_USERS_FILE = 'api/database/oauth_users.json'
ENTITIES_FILE = 'api/database/temp_entities.json'
# function that validates email format
def validate_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.fullmatch(pattern, email) is not None


def is_valid_phone(phone):
    return re.match(r'^\+?[0-9]{8,15}$', phone) is not None


def _extract_token(cookie_name="access_token"):
    auth_header = request.headers.get("Authorization", "")
    bearer = auth_header.removeprefix("Bearer ").strip()
    if bearer:
        return bearer
    return request.cookies.get(cookie_name, "").strip()
