# from .main import main_bp

from .data import  data_bp
from .health import health_bp

def register_routes(app):
    # app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(data_bp, url_prefix="/api/data")
    app.register_blueprint(health_bp, url_prefix = "/health")