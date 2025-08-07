from flask import Flask
from flask_apscheduler import APScheduler
import requests
from flask_cors import CORS



scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    app.config.from_object("config")

    from .routes import register_routes
    register_routes(app)

     # Initialize the scheduler
    scheduler.init_app(app)
    scheduler.start()

    # Register your jobs
    @scheduler.task('cron', id='daily_job', hour=6, minute=57)
    def job():
        try:
            requests.get("http://localhost:5000/api/facebook/get_all_followers_and_likes")
            print(" Job executed")
        except Exception as e:
            print(" Job failed:", e)

    return app    
