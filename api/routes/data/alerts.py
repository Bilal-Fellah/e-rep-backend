from flask import request

from . import data_bp
from api.routes.main import success_response, error_response
from api.services.alert_service import AlertService
from api.utils.permissions import require_role


@data_bp.route("/alerts", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def list_alerts():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    status = request.args.get("status")
    event_type = request.args.get("event_type")
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)

    data = AlertService.list_alerts(
        user_id=user_id,
        status=status,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return success_response(data, 200)


@data_bp.route("/alerts/unread-count", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def unread_alert_count():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    return success_response({"unread": AlertService.unread_count(user_id)}, 200)


@data_bp.route("/alerts/<int:user_alert_id>/read", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def mark_alert_read(user_alert_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    ok = AlertService.mark_read(user_id, user_alert_id)
    if not ok:
        return error_response("Alert not found", 404)
    return success_response({"updated": True}, 200)


@data_bp.route("/alerts/<int:user_alert_id>/dismiss", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def dismiss_alert(user_alert_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    ok = AlertService.mark_dismissed(user_id, user_alert_id)
    if not ok:
        return error_response("Alert not found", 404)
    return success_response({"updated": True}, 200)


@data_bp.route("/alerts/read-all", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def mark_all_alerts_read():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    updated = AlertService.mark_all_read(user_id)
    return success_response({"updated_count": updated}, 200)


@data_bp.route("/alert-rules", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def list_alert_rules():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    return success_response(AlertService.list_rules(user_id), 200)


@data_bp.route("/alert-rules", methods=["POST"])
@require_role("admin", "registered", "subscribed")
def create_alert_rule():
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    payload = request.get_json(silent=True) or {}
    try:
        return success_response(AlertService.create_rule(user_id, payload), 201)
    except ValueError as e:
        return error_response(str(e), 400)


@data_bp.route("/alert-rules/<int:rule_id>", methods=["PUT"])
@require_role("admin", "registered", "subscribed")
def update_alert_rule(rule_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    payload = request.get_json(silent=True) or {}
    try:
        updated = AlertService.update_rule(user_id, rule_id, payload)
    except ValueError as e:
        return error_response(str(e), 400)

    if not updated:
        return error_response("Rule not found", 404)
    return success_response(updated, 200)


@data_bp.route("/alert-rules/<int:rule_id>", methods=["DELETE"])
@require_role("admin", "registered", "subscribed")
def delete_alert_rule(rule_id: int):
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return error_response("User context not found", 401)

    deleted = AlertService.delete_rule(user_id, rule_id)
    if not deleted:
        return error_response("Rule not found", 404)
    return success_response({"deleted": True}, 200)
