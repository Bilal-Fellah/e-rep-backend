import json
import logging
import traceback
from datetime import datetime, timezone

from flask import current_app, has_app_context, has_request_context, jsonify, request
import jwt
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException


DB_ERROR_MESSAGE = "An error occurred in the database."
SERVER_ERROR_MESSAGE = "An error occurred in the server."
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
MAX_LOG_BODY_LENGTH = 4000
SENSITIVE_FIELDS = {
    "password",
    "token",
    "authorization",
    "access_token",
    "refresh_token",
    "secret",
    "client_secret",
    "id_token",
}

fallback_logger = logging.getLogger("route_errors")


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code

def success_response(data, status_code=200):
    return jsonify({"success": True, "data": data}), status_code


def db_error_response(status_code=500):
    return jsonify({"success": False, "error": DB_ERROR_MESSAGE}), status_code


def server_error_response(status_code=500):
    return jsonify({"success": False, "error": SERVER_ERROR_MESSAGE}), status_code


def _truncate_text(value, max_length=MAX_LOG_BODY_LENGTH):
    if not isinstance(value, str):
        value = str(value)
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...[truncated]"


def _redact_sensitive_values(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, nested_value in value.items():
            lowered_key = key.lower() if isinstance(key, str) else ""
            if lowered_key in SENSITIVE_FIELDS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _redact_sensitive_values(nested_value)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [_redact_sensitive_values(item) for item in value]

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return _truncate_text(value)


def _extract_request_data():
    if not has_request_context():
        return {}

    request_data = {}

    json_body = request.get_json(silent=True)
    if json_body is not None:
        request_data["json"] = _redact_sensitive_values(json_body)

    form_data = request.form.to_dict(flat=False)
    if form_data:
        request_data["form"] = _redact_sensitive_values(form_data)

    query_params = request.args.to_dict(flat=False)
    if query_params:
        request_data["query_params"] = _redact_sensitive_values(query_params)

    if request.view_args:
        request_data["path_params"] = _redact_sensitive_values(request.view_args)

    if "json" not in request_data and "form" not in request_data:
        raw_body = request.get_data(cache=True, as_text=True)
        if raw_body:
            request_data["raw_body"] = _truncate_text(raw_body)

    return request_data


def _build_stack_trace(error):
    if error is None:
        return None

    if getattr(error, "__traceback__", None):
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    return _truncate_text(error)


def log_route_error(error, severity, status_code, public_message):
    error_payload = {
        "timestamp": _utc_now_iso(),
        "severity": severity,
        "category": "route_error",
        "status_code": status_code,
        "public_message": public_message,
        "error_type": type(error).__name__ if error else None,
        "error_message": _truncate_text(error) if error else None,
        "stack_trace": _build_stack_trace(error),
    }

    if has_request_context():
        error_payload["request"] = {
            "request_id": request.headers.get("X-Request-ID"),
            "method": request.method,
            "url": request.url,
            "path": request.path,
            "endpoint": request.endpoint,
            "blueprint": request.blueprint,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string,
            "content_type": request.content_type,
            "data": _extract_request_data(),
        }

    logger = current_app.extensions.get("route_error_logger") if has_app_context() else fallback_logger
    if logger is None:
        logger = fallback_logger
    serialized = json.dumps(error_payload, ensure_ascii=True, default=str)

    if severity == SEVERITY_LOW:
        logger.warning(serialized)
    elif severity == SEVERITY_MEDIUM:
        logger.error(serialized)
    else:
        logger.critical(serialized)


def register_blueprint_error_handlers(blueprint, include_token_errors=False):
    if include_token_errors:
        @blueprint.errorhandler(jwt.ExpiredSignatureError)
        def handle_expired_signature(error):
            log_route_error(error, SEVERITY_MEDIUM, 401, "Token has expired")
            return error_response("Token has expired", 401)

        @blueprint.errorhandler(jwt.InvalidTokenError)
        def handle_invalid_token(error):
            log_route_error(error, SEVERITY_MEDIUM, 401, "Invalid token")
            return error_response("Invalid token", 401)

    @blueprint.errorhandler(BadRequest)
    def handle_bad_request(error):
        log_route_error(error, SEVERITY_LOW, 400, "Invalid request payload")
        return error_response("Invalid request payload", 400)

    @blueprint.errorhandler(TypeError)
    @blueprint.errorhandler(KeyError)
    @blueprint.errorhandler(ValueError)
    def handle_invalid_data(error):
        log_route_error(error, SEVERITY_LOW, 400, "Invalid request data")
        return error_response("Invalid request data", 400)

    @blueprint.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        log_route_error(error, SEVERITY_HIGH, 500, DB_ERROR_MESSAGE)
        return db_error_response(500)

    @blueprint.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            http_severity = SEVERITY_HIGH if error.code and error.code >= 500 else SEVERITY_MEDIUM
            log_route_error(error, http_severity, error.code, error.description)
            return error_response(error.description, error.code)

        log_route_error(error, SEVERITY_HIGH, 500, SERVER_ERROR_MESSAGE)
        return server_error_response(500)