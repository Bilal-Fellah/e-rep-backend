# Route wiring for testing-only endpoints.
from flask import Blueprint
from api.routes.main import register_blueprint_error_handlers

testing_bp = Blueprint("testing", __name__)

from . import entity_debug

register_blueprint_error_handlers(testing_bp, include_token_errors=True)
