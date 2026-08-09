# Data API endpoints for pages history monitoring.
from flask import request
from api.routes.main import error_response, success_response
from api.services.page_history_service import PageHistoryService
from api.utils.permissions import require_role
from . import data_bp


@data_bp.route("/pages_history", methods=["GET"])
@data_bp.route("/get_pages_history", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_pages_history():
    """
    Get paginated pages_history records with filtering by dates, brand, platform, page_id, and search keyword.
    """
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        brand_id_raw = request.args.get("brand_id") or request.args.get("entity_id")
        brand_id = None
        if brand_id_raw is not None:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                return error_response("Invalid query parameter: 'brand_id' must be an integer.", 400)

        brand_name = request.args.get("brand") or request.args.get("brand_name")
        platform = request.args.get("platform")
        page_id = request.args.get("page_id")
        search = request.args.get("search")

        try:
            page = int(request.args.get("page", 1))
            per_page = int(request.args.get("per_page", 20))
        except ValueError:
            return error_response("Invalid query parameters: 'page' and 'per_page' must be integers.", 400)

        sort_by = request.args.get("sort_by", "recorded_at")
        sort_order = request.args.get("sort_order", "desc")

        include_data_raw = request.args.get("include_data", "true").lower()
        include_data = include_data_raw not in ("false", "0", "no")

        data = PageHistoryService.get_filtered_history(
            start_date=start_date,
            end_date=end_date,
            brand_id=brand_id,
            brand_name=brand_name,
            platform=platform,
            page_id=page_id,
            search=search,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            include_data=include_data,
        )

        return success_response(data, status_code=200)

    except Exception as e:
        return error_response(f"An unexpected error occurred: {str(e)}", 500)


@data_bp.route("/pages_history/<int:history_id>", methods=["GET"])
@data_bp.route("/get_pages_history_by_id", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_pages_history_by_id(history_id=None):
    """
    Get a single pages_history record by ID with page and brand details.
    """
    try:
        if history_id is None:
            raw_id = request.args.get("id")
            if not raw_id:
                return error_response("Missing required parameter: 'id'.", 400)
            try:
                history_id = int(raw_id)
            except ValueError:
                return error_response("Invalid parameter: 'id' must be an integer.", 400)

        history = PageHistoryService.get_history_by_id(history_id)
        if not history:
            return error_response(f"No pages_history record found with id {history_id}.", 404)

        return success_response(history, status_code=200)

    except Exception as e:
        return error_response(f"An unexpected error occurred: {str(e)}", 500)


@data_bp.route("/pages_history/options", methods=["GET"])
@data_bp.route("/get_pages_history_options", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_pages_history_options():
    """
    Get filter metadata options (platforms, brands, min/max dates, total count) for UI dropdowns.
    """
    try:
        options = PageHistoryService.get_filter_options()
        return success_response(options, status_code=200)
    except Exception as e:
        return error_response(f"An unexpected error occurred: {str(e)}", 500)


@data_bp.route("/pages_history/summary", methods=["GET"])
@data_bp.route("/get_pages_history_summary", methods=["GET"])
@require_role("admin", "registered", "subscribed")
def get_pages_history_summary():
    """
    Get monitoring aggregate statistics for pages_history data.
    """
    try:
        summary = PageHistoryService.get_monitoring_summary()
        return success_response(summary, status_code=200)
    except Exception as e:
        return error_response(f"An unexpected error occurred: {str(e)}", 500)
