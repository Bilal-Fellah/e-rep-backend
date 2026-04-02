import re

ALLOWED_ROLES = ["registered", "subscribed", "admin"]
ALLOWED_PROFESSIONS = ["community_manager", "marketing", "ceo", "journalist", "influencer", "student", "sales", "other"]


def validate_required_keys(data, required_keys):
    """Returns the first missing key, or None if all present."""
    if not data or not isinstance(data, dict):
        return "request body"
    for key in required_keys:
        if key not in data or data[key] is None:
            return key
    return None


def validate_enum(value, allowed, field_name):
    """Returns error message if value not in allowed list, else None."""
    if value not in allowed:
        return f"{field_name} must be one of {allowed}"
    return None


def sanitize_string(value, max_length=200):
    """Strips and truncates a string value."""
    if not isinstance(value, str):
        return None
    return value.strip()[:max_length]


def validate_email(email):
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.fullmatch(pattern, email) is not None


def validate_phone(phone):
    if not phone or not isinstance(phone, str):
        return False
    return re.match(r'^\+?[0-9]{8,15}$', phone) is not None


def validate_password(password):
    """Password must be at least 8 characters."""
    if not password or not isinstance(password, str):
        return False
    return len(password) >= 8
