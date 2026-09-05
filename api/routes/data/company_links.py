# Client-facing routes for asking to be linked to a company.
#
# The client can ask and can see the outcome; only an admin can approve
# (api/routes/admin_routes.py). See
# api/services/client_entity_link_service.py for why approval is manual.
from flask import request

from api.routes.data import data_bp
from api.routes.main import error_response, success_response
from api.services.client_entity_link_service import (
    ClientEntityLinkError,
    ClientEntityLinkService,
)
from api.utils.permissions import require_role


@data_bp.route("/company-links", methods=["GET"])
@require_role("registered", "subscribed", "admin")
def list_my_company_links():
    """Every company this client is linked to or has asked to join,
    including rejected requests and the reason given."""
    user_id = getattr(request, "user_id", None)
    return success_response({"links": ClientEntityLinkService.list_for_user(user_id)})


@data_bp.route("/company-links", methods=["POST"])
@require_role("registered", "subscribed", "admin")
def request_company_link():
    """Ask to be added to a company. Creates a pending request for an admin
    to review -- it does not link anything by itself."""
    payload = request.get_json() or {}

    entity_id = payload.get("entity_id")
    if entity_id is None:
        return error_response("Missing required field: 'entity_id'.", 400)

    try:
        result = ClientEntityLinkService.request_link(
            user_id=getattr(request, "user_id", None),
            entity_id=int(entity_id),
            note=payload.get("note"),
        )
    except (TypeError, ValueError) as exc:
        # ClientEntityLinkError subclasses ValueError; a non-integer
        # entity_id lands here too, and both are the caller's mistake.
        return error_response(str(exc), 400)

    return success_response(result, 201)


@data_bp.route("/company-links/<int:link_id>", methods=["DELETE"])
@require_role("registered", "subscribed", "admin")
def withdraw_company_link(link_id):
    """Take back a request that hasn't been answered yet."""
    try:
        result = ClientEntityLinkService.withdraw(
            user_id=getattr(request, "user_id", None), link_id=link_id
        )
    except ClientEntityLinkError as exc:
        return error_response(str(exc), 400)
    return success_response(result)
