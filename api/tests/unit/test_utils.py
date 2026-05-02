from datetime import date, datetime, timezone
import json
import uuid

import pytest
from flask import Flask

from api.utils.auth import _extract_token, is_valid_phone, validate_email as auth_validate_email
from api.utils.data_keys import compute_score
from api.utils.interaction_stats import interpolate_series
from api.utils.login_codes_utils import consume_login_code, store_login_code
from api.utils.page_uuid import create_page_uuid, normalize_page_link
from api.utils.posts_utils import _to_number, ensure_datetime, parse_relative_time
from api.utils.request_parsing import normalize_to_utc_datetime, parse_iso_date, today_date
from api.utils.validators import (
    validate_email,
    validate_enum,
    validate_password,
    validate_phone,
    validate_required_keys,
    sanitize_string,
)


def test_validate_required_keys_handles_missing_body_and_values():
    assert validate_required_keys(None, ["email"]) == "request body"
    assert validate_required_keys({}, ["email"]) == "request body"
    assert validate_required_keys({"email": None}, ["email"]) == "email"
    assert validate_required_keys({"email": "x@y.com"}, ["email"]) is None


def test_validate_enum_and_sanitize_string():
    assert validate_enum("admin", ["registered", "admin"], "role") is None
    assert validate_enum("guest", ["registered", "admin"], "role") == "role must be one of ['registered', 'admin']"

    assert sanitize_string("  hello  ") == "hello"
    assert sanitize_string("x" * 20, max_length=5) == "xxxxx"
    assert sanitize_string(100) is None


def test_validators_email_phone_password():
    assert validate_email("valid@example.com") is True
    assert validate_email("invalid") is False

    assert validate_phone("+212612345678") is True
    assert validate_phone("abc") is False

    assert validate_password("12345678") is True
    assert validate_password("short") is False

    assert validate_email(None) is False
    assert validate_phone(None) is False
    assert validate_password(None) is False

    assert validate_email(123) is False
    assert validate_phone(123) is False
    assert validate_password(123) is False


def test_auth_utils_email_phone_and_token_extraction():
    app = Flask(__name__)

    assert auth_validate_email("john@doe.com") is True
    assert auth_validate_email("john") is False
    assert is_valid_phone("+33612345678") is True
    assert is_valid_phone("+33abc") is False

    with app.test_request_context(headers={"Authorization": "Bearer token-from-header"}):
        assert _extract_token() == "token-from-header"

    with app.test_request_context(headers={}, environ_overrides={"HTTP_COOKIE": "access_token=cookie-token"}):
        assert _extract_token() == "cookie-token"

    with app.test_request_context(headers={}, environ_overrides={}):
        assert _extract_token() == ""


def test_compute_score_uses_weights_and_handles_none():
    post = {"likes": 10, "comments": None}
    metrics = [{"name": "likes", "weight": 0.5}, {"name": "comments", "weight": 2}]

    score, gains = compute_score(post, metrics)

    assert score == 5.0
    assert gains == {"likes": 10, "comments": None}


def test_interpolate_series_fills_gaps_with_neighbors_or_previous():
    assert interpolate_series([5, 0, 15]) == [5, 10.0, 15]
    assert interpolate_series([5, None, None]) == [5, 5, 5]
    assert interpolate_series([0, None, 10]) == [0, 10, 10]
    assert interpolate_series([0, None, 0]) == [0, 0, 0]


def test_page_uuid_normalization_and_uuid_generation_are_stable():
    link = " HTTPS://m.Example.com/Page/?ref=abc "
    normalized = normalize_page_link(link)

    assert normalized == "https://www.example.com/page"

    page_uuid = create_page_uuid(link)
    assert isinstance(page_uuid, uuid.UUID)
    assert page_uuid == uuid.uuid5(uuid.NAMESPACE_URL, normalized)


def test_login_codes_store_and_consume_with_expiration(tmp_path, monkeypatch):
    from api.utils import login_codes_utils as login_utils

    file_path = tmp_path / "codes.json"
    monkeypatch.setattr(login_utils, "LOGIN_CODE_FILE", str(file_path))

    now = 1_700_000_000.0
    monkeypatch.setattr(login_utils.time, "time", lambda: now)

    store_login_code("good", 1, ttl=60)
    store_login_code("expired", 2, ttl=-1)

    assert consume_login_code("good") == {"user_id": 1, "exp": now + 60}
    assert consume_login_code("expired") is None
    assert consume_login_code("missing") is None


def test_login_codes_cleanup_persists_only_unexpired_entries(tmp_path, monkeypatch):
    from api.utils import login_codes_utils as login_utils

    file_path = tmp_path / "codes.json"
    monkeypatch.setattr(login_utils, "LOGIN_CODE_FILE", str(file_path))

    now = 1_700_000_000.0
    monkeypatch.setattr(login_utils.time, "time", lambda: now)

    with open(file_path, "w") as f:
        json.dump(
            {
                "expired": {"user_id": 1, "exp": now - 1},
                "alive": {"user_id": 2, "exp": now + 120},
            },
            f,
        )

    assert consume_login_code("missing") is None

    with open(file_path, "r") as f:
        saved = json.load(f)

    assert "expired" not in saved
    assert saved["alive"]["user_id"] == 2


def test_parse_relative_time_and_number_casting():
    parsed = parse_relative_time("2 day ago")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert _to_number("12") == 12
    assert _to_number("12.8") == 12
    assert _to_number("abc") == 0
    assert parse_relative_time("yesterday") is None


def test_ensure_datetime_with_naive_aware_string_and_invalid_type():
    naive = datetime(2025, 1, 1, 10, 0, 0)
    aware = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    assert ensure_datetime(naive).tzinfo is not None
    assert ensure_datetime(aware).tzinfo is not None
    assert ensure_datetime("2025-01-01T10:00:00Z").tzinfo is not None

    with pytest.raises(TypeError):
        ensure_datetime(123)


def test_request_parsing_helpers(monkeypatch):
    parsed_date = parse_iso_date("2025-01-15T00:00:00Z")
    parsed_dt = normalize_to_utc_datetime("2025-01-15T08:30:00Z")

    assert parsed_date.isoformat() == "2025-01-15"
    assert parsed_dt.tzinfo is not None
    assert parse_iso_date(None) is None
    assert normalize_to_utc_datetime(None) is None

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2030, 1, 2)

    from api.utils import request_parsing as rp
    monkeypatch.setattr(rp, "date", _FakeDate)
    assert today_date().isoformat() == "2030-01-02"