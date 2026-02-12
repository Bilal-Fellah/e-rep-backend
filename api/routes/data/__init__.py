from flask import Blueprint

data_bp = Blueprint("data", __name__)

from . import entity, page, category, influence_history, posts  # import your route files

