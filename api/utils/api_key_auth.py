# API key authentication utilities.
import hmac
import os
import time
from functools import wraps
from flask import request
from api.routes.main import error_response


# Simple in-memory rate limiting (per API key)
# Structure: {scope:api_key: {"count": int, "reset_time": float}}
rate_limit_store = {}
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


def _require_bearer_api_key(*, env_var: str, scope: str, error_message: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return error_response(error_message, 401)

            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return error_response(error_message, 401)

            provided_key = parts[1]
            expected_key = os.getenv(env_var)
            if not expected_key:
                return error_response(error_message, 401)

            # Constant-time comparison to avoid timing side-channel leakage.
            if not hmac.compare_digest(
                provided_key.encode("utf-8"), expected_key.encode("utf-8")
            ):
                return error_response(error_message, 401)

            current_time = time.time()
            store_key = f"{scope}:{provided_key}"

            if store_key in rate_limit_store:
                limit_data = rate_limit_store[store_key]
                if current_time >= limit_data["reset_time"]:
                    rate_limit_store[store_key] = {
                        "count": 1,
                        "reset_time": current_time + RATE_LIMIT_WINDOW,
                    }
                else:
                    if limit_data["count"] >= RATE_LIMIT_REQUESTS:
                        retry_after = int(limit_data["reset_time"] - current_time)
                        return error_response(
                            f"Rate limit exceeded. Try again in {retry_after} seconds.",
                            429,
                        )
                    limit_data["count"] += 1
            else:
                rate_limit_store[store_key] = {
                    "count": 1,
                    "reset_time": current_time + RATE_LIMIT_WINDOW,
                }

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_api_key(func):
    """
    Scraping-service API key auth.
    Expects Authorization: Bearer <SCRAPING_API_KEY>
    """
    return _require_bearer_api_key(
        env_var="SCRAPING_API_KEY",
        scope="scraping",
        error_message="Invalid or missing API key",
    )(func)


def require_alerts_engine_api_key(func):
    """
    Alerts-engine service API key auth.
    Expects Authorization: Bearer <ALERTS_ENGINE_API_KEY>
    """
    return _require_bearer_api_key(
        env_var="ALERTS_ENGINE_API_KEY",
        scope="alerts_engine",
        error_message="Invalid or missing alerts engine API key",
    )(func)
