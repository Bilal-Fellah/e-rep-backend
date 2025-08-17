from flask import Flask
from flask_cors import CORS
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

    
    # ---- Config ----
    app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{DB_USER}:{DB_PWD}@{VPS_ADDRESS}:{VPS_DB_PORT}/{DB_NAME}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # ---- Import models so Alembic sees them ----
    from api import models

    
    # Get environment
    environment = os.environ.get('FLASK_ENV', 'development')
    
    # Configure CORS based on environment
    if environment == 'production':
        # Production: Only allow requests from your Vercel app
        CORS(app, 
             resources={r"/api/*": {
                 "origins": "https://erep.vercel.app",  # Only allow this specific origin
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                 "allow_headers": ["Content-Type", "Authorization", "Accept"],
                 "supports_credentials": False
             }})
    else:
        # Development: Allow all origins
        CORS(app, 
             resources={r"/api/*": {
                 "origins": "*",
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                 "allow_headers": ["Content-Type", "Authorization", "Accept"],
                 "supports_credentials": False
             }})

    from .routes import register_routes
    register_routes(app)

    
    return app