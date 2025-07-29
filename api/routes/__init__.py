# from .main import main_bp
from .facebook_likes_followers import fb_bp
from .linkedin_followers import linkedin_bp
from .data import  data_bp

def register_routes(app):
    # app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(fb_bp, url_prefix="/api/facebook")
    app.register_blueprint(data_bp, url_prefix="/api/data")
    app.register_blueprint(linkedin_bp, url_prefix="/api/linkedin")