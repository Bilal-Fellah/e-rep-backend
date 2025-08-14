from flask import Flask
from flask_cors import CORS
import requests
from flask_cors import CORS
import os



def create_app():
    app = Flask(__name__)


    app.config.from_object("config")
    
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