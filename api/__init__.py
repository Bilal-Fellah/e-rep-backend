from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import math
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, JSON, UUID

from .utils.logging_utils import configure_error_loggers

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(JSON, "sqlite")
def compile_json_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


TRUNCATE_FLOAT_DECIMALS = 2


def _truncate_float(value: float, decimals: int = TRUNCATE_FLOAT_DECIMALS) -> float:
    factor = 10 ** decimals
    return math.trunc(value * factor) / factor


def _truncate_floats(value):
    if isinstance(value, float):
        if math.isfinite(value):
            return _truncate_float(value)
        return value

    if isinstance(value, dict):
        return {key: _truncate_floats(val) for key, val in value.items()}

    if isinstance(value, list):
        return [_truncate_floats(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_truncate_floats(item) for item in value)

    return value


class TruncatingJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        return super().dumps(_truncate_floats(obj), **kwargs)


# create db object (but don't bind to app yet)
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.json_provider_class = TruncatingJSONProvider
    app.json = app.json_provider_class(app)

    VPS_ADDRESS = os.getenv("VPS_ADDRESS")
    VPS_DB_PORT = os.getenv("VPS_DB_PORT")
    DB_USER = os.getenv("DB_USER")
    DB_PWD = os.getenv("DB_PWD")
    DB_NAME = os.getenv("DB_NAME")
    environment = os.getenv("FLASK_ENV", "development").lower()

    # ---- Config ----
    if os.getenv("TESTING") == "true" or environment == "testing":
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    elif environment == "production":
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"postgresql://{DB_USER}:{DB_PWD}@/{DB_NAME}"
            f"?host=/var/run/postgresql"
        )
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            f"postgresql://{DB_USER}:{DB_PWD}@{VPS_ADDRESS}:{VPS_DB_PORT}/{DB_NAME}"
        )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.secret_key = os.getenv("SECRET_KEY")

    # SameSite/Secure come from one place so the browser-rejected
    # SameSite=None-without-Secure pair can't be emitted. Defaults are
    # None + Secure, which is what the Google redirect needs.
    from api.utils.cookie_policy import COOKIE_SAMESITE, COOKIE_SECURE

    app.config.update(
        SESSION_COOKIE_NAME="brendex_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=COOKIE_SECURE,
    )



    db.init_app(app)
    migrate.init_app(app, db)
    configure_error_loggers(app)

    # ---- Import models so Alembic sees them ----
    from api.models import (  # noqa: F401
        Entity,
        Category,
        Page,
        PageHistory,
        EntityCategory,
        User,
        Note,
        AiInsightCache,
        PreapprovedMail,
        Subscription,
        AlertRule,
        AlertRuleKeyword,
        AlertEvent,
        UserAlert,
        AlertDetectorCheckpoint,
    )

    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5000",
        "https://www.brendex.net",
        "https://www.app.brendex.net",
        "https://brendex.net",
        "https://app.brendex.net",
        "https://admin.brendex.net",
    ]

    CORS(app,
        resources={r"/api/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "Accept"],
            "supports_credentials": True
        }}
    )

    from .routes import register_routes
    register_routes(app)

    # ---- CLI: refresh the metrics materialized view after a daily scrape ----
    @app.cli.command("refresh-mv")
    def refresh_mv():
        """Refresh page_posts_metrics_mv, posts_history_mv, and posts_mv so API reads reflect the latest scrape.

        Run this from the same cron as the daily scrape, e.g.:
            flask refresh-mv
        """
        from api.repositories.page_history_repository import PageHistoryRepository
        from api.services.alert_engine_service import AlertEngineService

        PageHistoryRepository.refresh_metrics_mv()
        AlertEngineService.mark_mv_refreshed()
        app.logger.info("Materialized views (page_posts_metrics_mv, posts_history_mv, posts_mv) refreshed successfully")
        print("Materialized views refreshed successfully")

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        from api.routes.main import db_error_response

        return db_error_response(500)

    @app.errorhandler(Exception)
    def handle_unhandled_error(error):
        if isinstance(error, HTTPException):
            return error

        from api.routes.main import server_error_response

        return server_error_response(500)
    
    return app