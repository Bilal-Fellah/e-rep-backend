from flask import Blueprint, request
from sqlalchemy.exc import SQLAlchemyError

from api.routes.main import (
    error_response,
    success_response,
    db_error_response,
    server_error_response,
    register_blueprint_error_handlers,
    log_route_error,
    SEVERITY_LOW,
    SEVERITY_HIGH,
)
from api.services.alert_engine_service import AlertEngineService
from api.utils.api_key_auth import require_alerts_engine_api_key


alerts_engine_bp = Blueprint("alerts_engine", __name__, url_prefix="/api/alerts/engine")
register_blueprint_error_handlers(alerts_engine_bp)


@alerts_engine_bp.route("/readiness", methods=["GET"])
@require_alerts_engine_api_key
def get_readiness():
    """Readiness for alert detectors based on existing ingestion data."""
    try:
        return success_response(AlertEngineService.get_readiness(), 200)
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during alerts readiness check")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during alerts readiness check")
        return server_error_response(500)


@alerts_engine_bp.route("/run", methods=["POST"])
@require_alerts_engine_api_key
def run_detectors():
    """Run alert detectors. Intended for external timer-based orchestrator."""
    try:
        payload = request.get_json(silent=True) or {}
        detectors = payload.get("detectors")
        dry_run = bool(payload.get("dry_run", False))

        if detectors is not None and not isinstance(detectors, list):
            return error_response("detectors must be an array", 400)

        result = AlertEngineService.run(detectors=detectors, dry_run=dry_run)
        return success_response(result, 200)
    except ValueError as e:
        log_route_error(e, SEVERITY_LOW, 400, "Invalid request data")
        return error_response(str(e), 400)
    except SQLAlchemyError as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Database error during alerts detector run")
        return db_error_response(500)
    except Exception as e:
        log_route_error(e, SEVERITY_HIGH, 500, "Unexpected error during alerts detector run")
        return server_error_response(500)
