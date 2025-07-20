from .main import main_bp
from .facebook_likes_followers import fb_bp
from .tables import  fill_bp

def register_routes(app):
    app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(fb_bp, url_prefix="/api/facebook")
    app.register_blueprint(fill_bp, url_prefix="/api/fill")