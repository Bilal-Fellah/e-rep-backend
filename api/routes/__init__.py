# from .main import main_bp

from .data import  data_bp

def register_routes(app):
    # app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(data_bp, url_prefix="/api/data")
   