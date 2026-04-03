from flask import jsonify
import jwt
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, HTTPException


DB_ERROR_MESSAGE = "An error occurred in the database."
SERVER_ERROR_MESSAGE = "An error occurred in the server."

def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code

def success_response(data, status_code=200):
    return jsonify({"success": True, "data": data}), status_code


def db_error_response(status_code=500):
    return jsonify({"success": False, "error": DB_ERROR_MESSAGE}), status_code


def server_error_response(status_code=500):
    return jsonify({"success": False, "error": SERVER_ERROR_MESSAGE}), status_code


def register_blueprint_error_handlers(blueprint, include_token_errors=False):
    if include_token_errors:
        @blueprint.errorhandler(jwt.ExpiredSignatureError)
        def handle_expired_signature(error):
            return error_response("Token has expired", 401)

        @blueprint.errorhandler(jwt.InvalidTokenError)
        def handle_invalid_token(error):
            return error_response("Invalid token", 401)

    @blueprint.errorhandler(BadRequest)
    def handle_bad_request(error):
        return error_response("Invalid request payload", 400)

    @blueprint.errorhandler(TypeError)
    @blueprint.errorhandler(KeyError)
    @blueprint.errorhandler(ValueError)
    def handle_invalid_data(error):
        return error_response("Invalid request data", 400)

    @blueprint.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        return db_error_response(500)

    @blueprint.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error_response(error.description, error.code)
        return server_error_response(500)