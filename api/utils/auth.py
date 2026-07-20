# Shared helper functions for auth.
import json
import os
import re
from flask import request

MAILS_FILE = 'api/database/tem_mail_registeration.json'
OAUTH_USERS_FILE = 'api/database/oauth_users.json'
ENTITIES_FILE = 'api/database/temp_entities.json'


def read_json_list(path):
    """Read a JSON list from `path`, returning [] when the file is absent or
    empty. The api/database/*.json files are gitignored runtime data, so a fresh
    deployment starts without them (only the directory ships)."""
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        content = f.read().strip()
    return json.loads(content) if content else []


def append_json_list(path, item):
    """Append `item` to the JSON list at `path`, creating the file (and parent
    directory) if it does not exist yet."""
    items = read_json_list(path)
    items.append(item)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        json.dump(items, f, indent=4)


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
