import logging
import os

# from .main import main_bp

from .data import data_bp
from .health import health_bp
from .auth_routes import auth_bp
from .google_auth import oauth_bp
from .public_routes import public_bp
from .scraping_routes import scraping_bp
from .admin_routes import admin_bp

try:
    from .testing import testing_bp
except ModuleNotFoundError:
    testing_bp = None
    logging.getLogger(__name__).warning(
        "Testing routes are unavailable; skipping /api/testing registration."
    )

def register_routes(app):
    # app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(data_bp, url_prefix="/api/data")
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(oauth_bp, url_prefix="/api/oauth")
    app.register_blueprint(public_bp, url_prefix="/api/public")
    app.register_blueprint(scraping_bp, url_prefix="/api/scraping")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    # The /api/testing routes are unauthenticated and mutate the DB (rewrite
    # entity categories, page URLs); never mount them in production.
    env = os.getenv("FLASK_ENV", "development").lower()
    if testing_bp is not None and env in ("development", "testing"):
        app.register_blueprint(testing_bp, url_prefix="/api/testing")
    elif testing_bp is not None:
        logging.getLogger(__name__).info(
            "Skipping /api/testing registration in %s environment.", env
        )