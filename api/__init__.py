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

    # ---- Config ----
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://bilal:bilal7230@135.181.66.165:5432/erep-db"
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