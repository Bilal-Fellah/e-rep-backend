# Shared helper functions for validators.
import re
import unicodedata

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


_PHONE_PATTERN = re.compile(r"\+?[0-9]{8,15}")

# Separators stripped before matching: whitespace, the spacing our own
# placeholder shows ("+1 234 567 8900"), and the invisible bidi marks that
# Arabic/RTL keyboards insert around a leading "+".
_PHONE_SEPARATORS = "-.()"

# Arabic-Indic and extended Arabic-Indic digits, which NFKC does not fold.
_ARABIC_DIGITS = str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
                              "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9",
                              "01234567890123456789")


def normalize_phone(phone):
    """Strips formatting noise from a phone number, returning the bare +digits form.

    Returns None for non-strings. This runs before validate_phone so that a
    number is judged on its digits, not on how the user's keyboard spaced it.
    """
    if not isinstance(phone, str):
        return None
    cleaned = unicodedata.normalize("NFKC", phone).translate(_ARABIC_DIGITS)
    # Drop whitespace, common separators, and invisible format characters.
    return "".join(
        ch for ch in cleaned
        if not ch.isspace() and ch not in _PHONE_SEPARATORS and unicodedata.category(ch) != "Cf"
    )


def validate_phone(phone):
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    return _PHONE_PATTERN.fullmatch(normalized) is not None


def validate_password(password):
    """Password must be at least 8 characters."""
    if not password or not isinstance(password, str):
        return False
    return len(password) >= 8
