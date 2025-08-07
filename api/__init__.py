from flask import Flask
from flask_cors import CORS
from flask_apscheduler import APScheduler
import requests
import os

scheduler = APScheduler()

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

    # Initialize the scheduler
    scheduler.init_app(app)
    scheduler.start()
    
    # Register your jobs (unchanged)
    @scheduler.task('cron', id='daily_job', hour=6, minute=57)
    def job():
        try:
            requests.get("http://localhost:5000/api/facebook/get_all_followers_and_likes")
            print("Job executed")
        except Exception as e:
            print("Job failed:", e)

    return app