from flask import Flask
from flask_cors import CORS
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .utils.logging_utils import configure_error_loggers

# create db object (but don't bind to app yet)
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    VPS_ADDRESS = os.getenv("VPS_ADDRESS")
    VPS_DB_PORT = os.getenv("VPS_DB_PORT")
    DB_USER = os.getenv("DB_USER")
    DB_PWD = os.getenv("DB_PWD")
    DB_NAME = os.getenv("DB_NAME")
    environment = os.getenv("FLASK_ENV", "development").lower()

    # ---- Config ----
    if environment == "production":
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

    app.config.update(
        SESSION_COOKIE_NAME="brendex_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="None",  # REQUIRED for Google redirect
        SESSION_COOKIE_SECURE=True,      # REQUIRED for SameSite=None
    )



    db.init_app(app)
    migrate.init_app(app, db)
    configure_error_loggers(app)

    # ---- Import models so Alembic sees them ----

    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5000",
        "https://www.brendex.net",
        "https://www.app.brendex.net",
        "https://brendex.net",
        "https://app.brendex.net",
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