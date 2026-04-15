# Shared helper functions for logging utils.
import logging
import os
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import current_app, has_app_context, has_request_context, request

try:
    from sqlalchemy.exc import SQLAlchemyError
except Exception:  # pragma: no cover
    SQLAlchemyError = tuple()


SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
MAX_TEXT_LENGTH = 4000
MAX_ARGUMENTS = 20
MAX_SERIALIZATION_DEPTH = 3
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


class UTCMonthlySizeRotatingFileHandler(RotatingFileHandler):
    """Rotate when month changes (UTC) or file exceeds maxBytes."""

    def __init__(
        self,
        log_dir,
        file_prefix,
        max_bytes=100 * 1024 * 1024,
        backup_count=10,
        encoding="utf-8",
    ):
        self.log_dir = Path(log_dir)
        self.file_prefix = file_prefix
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.current_period = self._current_utc_period()
        file_path = self._period_file_path(self.current_period)

        super().__init__(
            filename=file_path,
            mode="a",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
            delay=False,
        )

    def _current_utc_period(self):
        now_utc = datetime.now(timezone.utc)
        return f"{now_utc.year:04d}-{now_utc.month:02d}"

    def _period_file_path(self, period):
        return str(self.log_dir / f"{self.file_prefix}-{period}.jsonl")

    def _switch_to_period_file(self, period):
        if self.stream:
            self.stream.close()
            self.stream = None

        self.current_period = period
        self.baseFilename = os.path.abspath(self._period_file_path(period))
        self.stream = self._open()

    def shouldRollover(self, record):
        period = self._current_utc_period()
        if period != self.current_period:
            return 1

        return super().shouldRollover(record)

    def doRollover(self):
        period = self._current_utc_period()
        if period != self.current_period:
            self._switch_to_period_file(period)
            return

        super().doRollover()


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _truncate_text(value, max_length=MAX_TEXT_LENGTH):
    if not isinstance(value, str):
        value = str(value)
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}...[truncated]"


def _serialize_value(value, depth=0):
    if depth >= MAX_SERIALIZATION_DEPTH:
        return "[depth-limited]"

    if isinstance(value, dict):
        output = {}
        for idx, (key, nested_value) in enumerate(value.items()):
            if idx >= MAX_ARGUMENTS:
                output["...truncated"] = "[truncated]"
                break

            key_text = str(key)
            lowered_key = key_text.lower()
            if lowered_key in SENSITIVE_FIELDS:
                output[key_text] = "[REDACTED]"
            else:
                output[key_text] = _serialize_value(nested_value, depth + 1)
        return output

    if isinstance(value, (list, tuple, set)):
        values = list(value)
        serialized = [_serialize_value(item, depth + 1) for item in values[:MAX_ARGUMENTS]]
        if len(values) > MAX_ARGUMENTS:
            serialized.append("[truncated]")
        return serialized

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    if isinstance(value, str):
        return _truncate_text(value)

    return _truncate_text(repr(value))


def _build_stack_trace(error):
    if error is None:
        return None

    if getattr(error, "__traceback__", None):
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    return _truncate_text(error)


def _safe_request_data():
    if not has_request_context():
        return None

    payload = {
        "request_id": request.headers.get("X-Request-ID"),
        "method": request.method,
        "path": request.path,
        "endpoint": request.endpoint,
        "blueprint": request.blueprint,
    }

    request_json = request.get_json(silent=True)
    if request_json is not None:
        payload["json"] = _serialize_value(request_json)

    query_params = request.args.to_dict(flat=False)
    if query_params:
        payload["query_params"] = _serialize_value(query_params)

    return payload


def _determine_layer_severity(error):
    if SQLAlchemyError and isinstance(error, SQLAlchemyError):
        return SEVERITY_HIGH

    if isinstance(error, ValueError):
        return SEVERITY_LOW

    if isinstance(error, (TypeError, KeyError, AttributeError)):
        return SEVERITY_MEDIUM

    return SEVERITY_HIGH


def _get_logger(extension_key, fallback_name):
    if has_app_context():
        logger = current_app.extensions.get(extension_key)
        if logger is not None:
            return logger
    return logging.getLogger(fallback_name)


def _emit_layer_error(
    *,
    extension_key,
    fallback_name,
    category,
    class_name,
    method_name,
    error,
    method_type,
    args,
    kwargs,
):
    severity = _determine_layer_severity(error)

    normalized_args = list(args)
    if method_type in {"instance", "class"} and normalized_args:
        normalized_args = normalized_args[1:]

    payload = {
        "timestamp": _utc_now_iso(),
        "severity": severity,
        "category": category,
        "class_name": class_name,
        "method_name": method_name,
        "error_type": type(error).__name__,
        "error_message": _truncate_text(error),
        "stack_trace": _build_stack_trace(error),
        "call": {
            "method_type": method_type,
            "args": _serialize_value(normalized_args),
            "kwargs": _serialize_value(kwargs),
        },
    }

    request_payload = _safe_request_data()
    if request_payload:
        payload["request"] = request_payload

    logger = _get_logger(extension_key, fallback_name)
    serialized = json.dumps(payload, ensure_ascii=True, default=str)

    if severity == SEVERITY_LOW:
        logger.warning(serialized)
    elif severity == SEVERITY_MEDIUM:
        logger.error(serialized)
    else:
        logger.critical(serialized)


def _configure_layer_logger(
    app,
    *,
    logger_name,
    extension_key,
    file_prefix,
    log_dir_config_keys,
    max_bytes_config_key,
    backup_count_config_key,
):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    default_log_dir = os.path.abspath(os.path.join(app.root_path, "..", "logs"))
    log_dir = default_log_dir
    for key in log_dir_config_keys:
        config_value = app.config.get(key)
        if config_value:
            log_dir = config_value
            break

    max_bytes = int(app.config.get(max_bytes_config_key, 100 * 1024 * 1024))
    backup_count = int(app.config.get(backup_count_config_key, 12))

    has_handler = any(
        isinstance(handler, UTCMonthlySizeRotatingFileHandler) and file_prefix in handler.baseFilename
        for handler in logger.handlers
    )

    if not has_handler:
        handler = UTCMonthlySizeRotatingFileHandler(
            log_dir=log_dir,
            file_prefix=file_prefix,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    app.extensions[extension_key] = logger
    return logger


def configure_route_error_logger(app):
    return _configure_layer_logger(
        app,
        logger_name=app.config.get("ROUTE_ERROR_LOGGER_NAME", "route_errors"),
        extension_key="route_error_logger",
        file_prefix=app.config.get("ROUTE_ERROR_FILE_PREFIX", "route-errors"),
        log_dir_config_keys=["ROUTE_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
        max_bytes_config_key="ROUTE_ERROR_LOG_MAX_BYTES",
        backup_count_config_key="ROUTE_ERROR_LOG_BACKUP_COUNT",
    )


def configure_service_error_logger(app):
    return _configure_layer_logger(
        app,
        logger_name=app.config.get("SERVICE_ERROR_LOGGER_NAME", "service_errors"),
        extension_key="service_error_logger",
        file_prefix=app.config.get("SERVICE_ERROR_FILE_PREFIX", "service-errors"),
        log_dir_config_keys=["SERVICE_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
        max_bytes_config_key="SERVICE_ERROR_LOG_MAX_BYTES",
        backup_count_config_key="SERVICE_ERROR_LOG_BACKUP_COUNT",
    )


def configure_repository_error_logger(app):
    return _configure_layer_logger(
        app,
        logger_name=app.config.get("REPOSITORY_ERROR_LOGGER_NAME", "repository_errors"),
        extension_key="repository_error_logger",
        file_prefix=app.config.get("REPOSITORY_ERROR_FILE_PREFIX", "repository-errors"),
        log_dir_config_keys=["REPOSITORY_ERROR_LOG_DIR", "ERROR_LOG_DIR"],
        max_bytes_config_key="REPOSITORY_ERROR_LOG_MAX_BYTES",
        backup_count_config_key="REPOSITORY_ERROR_LOG_BACKUP_COUNT",
    )


def configure_error_loggers(app):
    return {
        "route": configure_route_error_logger(app),
        "service": configure_service_error_logger(app),
        "repository": configure_repository_error_logger(app),
    }


def _wrap_layer_callable(func, *, category, extension_key, fallback_name, class_name, method_name, method_type):
    if getattr(func, "__layer_logging_wrapped__", False):
        return func

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            _emit_layer_error(
                extension_key=extension_key,
                fallback_name=fallback_name,
                category=category,
                class_name=class_name,
                method_name=method_name,
                error=error,
                method_type=method_type,
                args=args,
                kwargs=kwargs,
            )
            raise

    wrapper.__layer_logging_wrapped__ = True
    return wrapper


def _instrument_layer_class(cls, *, category, extension_key, fallback_name):
    if getattr(cls, "__layer_logging_instrumented__", False):
        return cls

    for attribute_name, attribute_value in list(cls.__dict__.items()):
        if attribute_name.startswith("__") and attribute_name.endswith("__"):
            continue

        if isinstance(attribute_value, staticmethod):
            wrapped = _wrap_layer_callable(
                attribute_value.__func__,
                category=category,
                extension_key=extension_key,
                fallback_name=fallback_name,
                class_name=cls.__name__,
                method_name=attribute_name,
                method_type="static",
            )
            setattr(cls, attribute_name, staticmethod(wrapped))
            continue

        if isinstance(attribute_value, classmethod):
            wrapped = _wrap_layer_callable(
                attribute_value.__func__,
                category=category,
                extension_key=extension_key,
                fallback_name=fallback_name,
                class_name=cls.__name__,
                method_name=attribute_name,
                method_type="class",
            )
            setattr(cls, attribute_name, classmethod(wrapped))
            continue

        if callable(attribute_value):
            wrapped = _wrap_layer_callable(
                attribute_value,
                category=category,
                extension_key=extension_key,
                fallback_name=fallback_name,
                class_name=cls.__name__,
                method_name=attribute_name,
                method_type="instance",
            )
            setattr(cls, attribute_name, wrapped)

    cls.__layer_logging_instrumented__ = True
    return cls


def instrument_service_class(cls):
    return _instrument_layer_class(
        cls,
        category="service_error",
        extension_key="service_error_logger",
        fallback_name="service_errors",
    )


def instrument_repository_class(cls):
    return _instrument_layer_class(
        cls,
        category="repository_error",
        extension_key="repository_error_logger",
        fallback_name="repository_errors",
    )
