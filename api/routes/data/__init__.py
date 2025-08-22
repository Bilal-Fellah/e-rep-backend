from flask import Blueprint

data_bp = Blueprint("data", __name__)

from . import entity, page, category, influence_history  # import your route files

