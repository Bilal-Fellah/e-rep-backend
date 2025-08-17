# from .main import main_bp
from .scraping.facebook_likes_followers import fb_bp
from .scraping.linkedin_followers import linkedin_bp
from .scraping.instagram_followers_posts import instagram_bp
from .data import  data_bp
from .get_data_all import all_data_bp

def register_routes(app):
    # app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(fb_bp, url_prefix="/api/facebook")
    app.register_blueprint(data_bp, url_prefix="/api/data")
    app.register_blueprint(linkedin_bp, url_prefix="/api/linkedin")
    app.register_blueprint(instagram_bp, url_prefix="/api/instagram")
    app.register_blueprint(all_data_bp, url_prefix="/api/all_data")