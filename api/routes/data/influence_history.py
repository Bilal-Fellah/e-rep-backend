# Data API endpoints for influence history.
from datetime import datetime

from flask import request

from api.routes.main import error_response, success_response
from api.services.influence_history_service import InfluenceHistoryService
from api.utils.permissions import (
    current_user_role,
    limit_ranking_for_role,
    ranking_access_error,
)
from api.utils.posts_utils import ensure_datetime

from . import data_bp

@data_bp.route("/get_after_time", methods=["GET"])
def get_after_time():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        hour = int(request.args.get("hour"))

        history = InfluenceHistoryService.get_after_time(hour)
        if not history:
            return error_response("No history found", 404)

        data = [{'id': h.id, 'page_id': h.page_id, 'data': h.data} for h in history ]
        return success_response(data, 200)

    # except jwt.ExpiredSignatureError:
    #     return error_response("Token has expired", 401)
    # except jwt.InvalidTokenError:
    #     return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)

@data_bp.route("/get_today_pages_history", methods=["GET"])
def get_today_pages_history():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        history = InfluenceHistoryService.get_today_pages_history()
        if not history:
            return error_response("No history found", 404)

        data = [{'id': h.id, 'page_id': h.page_id, 'data': h.data} for h in history ]
        return success_response(data, 200)

#     except jwt.ExpiredSignatureError:
#         return error_response("Token has expired", 401)
#     except jwt.InvalidTokenError:
#         return error_response("Invalid token", 401)
    except Exception as e:
        return error_response(str(e), 500)


# @data_bp.route("/get_page_history_today", methods=["GET"])
# def get_page_history():
#     try:
#         # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
#         # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
#         # if not payload:
#         #     return error_response("No valid token has been sent", 401)
#         # role = payload['role']
#         # if role not in allowed_roles:
#         #     return error_response("Access denied", 403)

#         page_id = request.args.get("page_id")

#         history = InfluenceHistoryService.get_page_history_today(page_id)
#         if not history:
#             return error_response("No history found", 404)

#         data = {'id': history.id, 'page_id': history.page_id, 'data': history.data}
#         return success_response(data, 200)
#     except jwt.ExpiredSignatureError:
#         return error_response("Token has expired", 401)
#     except jwt.InvalidTokenError:
#         return error_response("Invalid token", 401)
#     except Exception as e:
#         return error_response(str(e), 500)


@data_bp.route("/get_platform_history", methods=["GET"])
def get_platform_history():
    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        platform = request.args.get("platform")
        if not platform:
            return error_response("Missing platform parameter", 400)
        history_list = InfluenceHistoryService.get_platform_history(platform)
        if not history_list:
            return error_response("No history found", 404)

        data = [
            {
                "id": h.id,
                "page_id": h.page_id,
                "data": h.data,
                "recorded_at": h.recorded_at,
            }
            for h in history_list
        ]
        return success_response(data, 200)
    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_entity_history", methods=["GET"])
def get_entity_history():
    """
    Fetch all page histories for a given entity_id (all pages belonging to entity).
    Optional: filter by date (default = today).
    """

    try:
        # token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        # payload = jwt.decode(token, SECRET, algorithms=['HS256'])
        # if not payload:
        #     return error_response("No valid token has been sent", 401)
        # role = payload['role']
        # if role not in allowed_roles:
        #     return error_response("Access denied", 403)

        entity_id = request.args.get("entity_id", type=int)
        date_str = request.args.get("date")

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        if date_str:
            try:
                datetime.fromisoformat(date_str)
            except ValueError:
                return error_response(
                    "Invalid date format. Use ISO format: YYYY-MM-DD.", 400
                )

        history = InfluenceHistoryService.get_entity_history(
            entity_id, date_str=date_str
        )
        if not history:
            return error_response("No history found for this entity.", 404)

        data = [
            {"id": h.id, "page_id": h.page_id, "data": h.data, "date": h.recorded_at}
            for h in history
        ]
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


# @data_bp.route("/get_entities_ranking", methods=["GET"])
# def get_entities_ranking():
#     # Deprecated in favor of /get_followers_ranking.
#     pass


@data_bp.route("/get_followers_ranking", methods=["GET"])
def get_followers_ranking():
    try:
        date_window = request.args.get("date")

        if not date_window:
            date_window = "1m"

        data = InfluenceHistoryService.get_followers_ranking(date_window=date_window)
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No followers ranking data found for entities.", 404)
        return success_response(data, 200)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except (TypeError, KeyError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_followers_progress_ranking", methods=["GET"])
def get_followers_progress_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_followers_progress_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(
                "No followers progress ranking data found for entities.", 404
            )

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_interactions_ranking", methods=["GET"])
def get_interactions_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_interactions_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(
                "No interactions ranking data found for companies.", 404
            )

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_likes_ranking", methods=["GET"])
def get_likes_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_likes_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No likes ranking data found for companies.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_comments_ranking", methods=["GET"])
def get_comments_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_comments_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No comments ranking data found for companies.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_posts_followers_ranking", methods=["GET"])
def get_posts_followers_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_posts_followers_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No followers ranking data found for posts.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_posts_interactions_ranking", methods=["GET"])
def get_posts_interactions_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_posts_interactions_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No interactions ranking data found for posts.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_posts_likes_ranking", methods=["GET"])
def get_posts_likes_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_posts_likes_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No likes ranking data found for posts.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_posts_comments_ranking", methods=["GET"])
def get_posts_comments_ranking():
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        period = request.args.get("period")

        role = current_user_role()
        access_error = ranking_access_error(role, start_date, end_date)
        if access_error:
            return error_response(access_error, 403)

        data = InfluenceHistoryService.get_posts_comments_ranking(
            period=period, start_date=start_date, end_date=end_date
        )
        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response("No comments ranking data found for posts.", 404)

        return success_response(limit_ranking_for_role(role, data), 200)

    except (TypeError, KeyError, ValueError) as exc:
        return error_response(
            str(exc) if "Invalid period" in str(exc) else "Invalid request data", 400
        )


@data_bp.route("/get_entity_interaction_stats", methods=["GET"])
def get_entity_interaction_stats():
    try:
        entity_id = request.args.get("entity_id", type=int)
        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        start_date = request.args.get("start_date")
        if start_date:
            start_date = datetime.fromisoformat(start_date)

        data = InfluenceHistoryService.get_entity_interaction_stats(
            entity_id, start_date=start_date
        )
        if not data:
            return error_response(f"No data found for entity {entity_id}.", 404)
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@data_bp.route("/get_competitors_interaction_stats", methods=["POST"])
def get_competitors_interaction_stats():

    try:
        inputs = request.get_json(silent=True) or {}

        entity_ids = inputs.get("entity_ids")
        if not isinstance(entity_ids, list) or not entity_ids:
            return error_response(
                "Invalid value for 'entity_ids'. Expected a non-empty list.", 400
            )

        start_date = inputs.get("start_date", None)
        # print(start_date)

        if start_date:
            start_date = ensure_datetime(start_date)
        else:
            start_date = None

        data = InfluenceHistoryService.get_competitors_interaction_stats(
            entity_ids, start_date=start_date
        )

        if not data or (isinstance(data, list) and len(data) < 1):
            return error_response(f"No data found for entity {entity_ids}.", 404)
        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
