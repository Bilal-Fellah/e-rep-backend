from flask import Blueprint, Flask
import jwt

from api.routes.main import error_response, register_blueprint_error_handlers, success_response


def test_success_and_error_response_helpers_shape_json():
    app = Flask(__name__)

    with app.app_context():
        ok_resp, ok_status = success_response({"k": "v"}, 201)
        err_resp, err_status = error_response("bad", 422)

        assert ok_status == 201
        assert ok_resp.get_json() == {"success": True, "data": {"k": "v"}}

        assert err_status == 422
        assert err_resp.get_json() == {"success": False, "error": "bad"}


def test_register_blueprint_error_handlers_maps_validation_and_token_errors():
    app = Flask(__name__)
    bp = Blueprint("bp_test", __name__)
    register_blueprint_error_handlers(bp, include_token_errors=True)

    @bp.route("/raise-value")
    def _raise_value():
        raise ValueError("x")

    @bp.route("/raise-token")
    def _raise_token():
        raise jwt.InvalidTokenError("bad token")

    app.register_blueprint(bp, url_prefix="/t")
    client = app.test_client()

    value_resp = client.get("/t/raise-value")
    assert value_resp.status_code == 400
    assert value_resp.get_json() == {"success": False, "error": "Invalid request data"}

    token_resp = client.get("/t/raise-token")
    assert token_resp.status_code == 401
    assert token_resp.get_json() == {"success": False, "error": "Invalid token"}
