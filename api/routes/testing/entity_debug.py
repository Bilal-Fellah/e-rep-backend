# Testing endpoints for inspecting raw entity metric snapshots.
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from flask import request

from api.repositories.category_repository import CategoryRepository
from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.routes.main import error_response, success_response
from api.utils.data_keys import platform_metrics
from api.utils.posts_utils import _to_number, ensure_datetime
from api.utils.request_parsing import parse_iso_date
from . import testing_bp


_LIKES_METRIC_KEY = {
    "instagram": "likes",
    "linkedin": "likes_count",
    "tiktok": "favorites_count",
    "x": "likes",
    "facebook": "likes",
}
_COMMENTS_METRIC_KEY = {
    "instagram": "comments",
    "linkedin": "comments_count",
    "tiktok": "commentcount",
    "x": "replies",
    "facebook": "num_comments",
}
_METRIC_ID_KEY = {
    "instagram": platform_metrics["instagram"]["id_key"],
    "linkedin": platform_metrics["linkedin"]["id_key"],
    "tiktok": platform_metrics["tiktok"]["id_key"],
    "x": platform_metrics["x"]["id_key"],
    "facebook": platform_metrics["facebook"]["id_key"],
}


def _build_metric_daily_raw_rows(rows, metric_key_by_platform, id_key_by_platform, output_key):
    if not rows:
        return []

    # Keep only recorded-day snapshots without interpolation/distribution.
    daily_posts = defaultdict(lambda: defaultdict(dict))

    for row in rows:
        platform = row.platform
        page_id = row.page_id
        recorded_at = ensure_datetime(row.recorded_at)
        posts_metrics = row.posts_metrics

        if platform not in metric_key_by_platform:
            continue
        if not posts_metrics:
            continue

        if isinstance(posts_metrics, list) and len(posts_metrics) > 0 and isinstance(posts_metrics[0], list):
            posts_metrics = sum(posts_metrics, [])
        elif isinstance(posts_metrics, dict):
            posts_metrics = [posts_metrics]

        if not isinstance(posts_metrics, list):
            continue

        day = recorded_at.date()
        for post in posts_metrics:
            if not isinstance(post, dict):
                continue

            post_id = post.get(id_key_by_platform[platform])
            if not post_id:
                continue

            metric_value = _to_number(post.get(metric_key_by_platform[platform], 0))
            daily_posts[(page_id, platform)][day][post_id] = metric_value

    data = []
    for (page_id, platform), day_posts in daily_posts.items():
        for day in sorted(day_posts.keys()):
            per_post = day_posts[day]
            data.append(
                {
                    "page_id": page_id,
                    "platform": platform,
                    "date": day.isoformat(),
                    output_key: sum(per_post.values()),
                    "posts_count": len(per_post),
                    "per_post": per_post,
                }
            )

    data.sort(key=lambda x: (x["date"], x["platform"], str(x["page_id"])))
    return data


def _fetch_entity_daily_raw_metrics(entity_id, metric="likes", start_date=None):
    date_limit = parse_iso_date(start_date) if start_date else datetime.now(timezone.utc).date() - timedelta(days=30)
    metric_name = (metric or "likes").lower()

    if metric_name == "comments":
        history = PageHistoryRepository().get_entity_comments_development(entity_id, date_limit=date_limit)
        return _build_metric_daily_raw_rows(
            history,
            metric_key_by_platform=_COMMENTS_METRIC_KEY,
            id_key_by_platform=_METRIC_ID_KEY,
            output_key="comments_raw",
        )

    history = PageHistoryRepository().get_entity_likes_development(entity_id, date_limit=date_limit)
    return _build_metric_daily_raw_rows(
        history,
        metric_key_by_platform=_LIKES_METRIC_KEY,
        id_key_by_platform=_METRIC_ID_KEY,
        output_key="likes_raw",
    )


def _replace_entity_category_mapping(entity_id, category_id):
    existing_relations = EntityCategoryRepository.get_by_entity(entity_id)
    previous_category_ids = [relation.category_id for relation in existing_relations]

    for relation in existing_relations:
        EntityCategoryRepository.delete(entity_id=entity_id, category_id=relation.category_id)

    new_relation = EntityCategoryRepository.add(entity_id=entity_id, category_id=category_id)
    return new_relation, previous_category_ids


@testing_bp.route("/entity_daily_raw_metrics", methods=["GET"])
def get_entity_daily_raw_metrics():
    try:
        entity_id = request.args.get("entity_id", type=int)
        metric = request.args.get("metric", default="likes")
        start_date = request.args.get("start_date")

        if not entity_id:
            return error_response("Missing required query param: 'entity_id'.", 400)

        if metric not in ("likes", "comments"):
            return error_response("Invalid metric. Use 'likes' or 'comments'.", 400)

        data = _fetch_entity_daily_raw_metrics(entity_id, metric=metric, start_date=start_date)
        if not data:
            return error_response("No daily raw metrics found for this entity.", 404)

        return success_response(data, 200)

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)


@testing_bp.route("/update_entity_category", methods=["POST"])
def update_entity_category():
    try:
        payload = request.get_json(silent=True) or {}
        entity_id = payload.get("entity_id")
        category_id = payload.get("category_id")

        if entity_id is None or category_id is None:
            return error_response("Missing required fields: 'entity_id' and 'category_id'.", 400)

        try:
            entity_id = int(entity_id)
            category_id = int(category_id)
        except (TypeError, ValueError):
            return error_response("'entity_id' and 'category_id' must be integers.", 400)

        entity = EntityRepository.get_by_id(entity_id)
        if not entity:
            return error_response(f"No entity found with id {entity_id}.", 404)

        category = CategoryRepository.get_by_id(category_id)
        if not category:
            return error_response(f"No category found with id {category_id}.", 404)

        relation, previous_category_ids = _replace_entity_category_mapping(entity_id, category_id)

        return success_response(
            {
                "entity_id": relation.entity_id,
                "previous_category_ids": previous_category_ids,
                "updated_category_id": relation.category_id,
            },
            200,
        )

    except (TypeError, KeyError, ValueError):
        return error_response("Invalid request data", 400)
