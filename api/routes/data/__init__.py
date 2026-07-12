from flask import Blueprint
from api.routes.main import register_blueprint_error_handlers

data_bp = Blueprint("data", __name__)

from . import entity, page, category, influence_history, note, posts  # import your route files

register_blueprint_error_handlers(data_bp, include_token_errors=True)

