# Business workflows for influence history service.
from collections import defaultdict
from datetime import datetime, date, timedelta

from api.repositories.page_history_repository import PageHistoryRepository
from api.utils.data_keys import platform_metrics
from api.utils.logging_utils import instrument_service_class
from api.utils.request_parsing import parse_iso_date
from api.utils.posts_utils import _to_number, ensure_datetime


@instrument_service_class
class InfluenceHistoryService:
    _METRIC_TOTAL_GROUPS = {
        "likes": {"likes", "likes_count", "favorites_count"},
        "comments": {"comments", "comments_count", "commentcount", "replies", "num_comments"},
        "shares": {"shares", "share_count", "reposts", "num_shares"},
        "views": {"views", "playcount", "view_count", "video_view_count"},
    }

    @staticmethod
    def _row_value(row, key, default=0):
        if isinstance(row, dict):
            return row.get(key, default)
        if hasattr(row, key):
            return getattr(row, key)
        try:
            return row[key]
        except Exception:
            return default

    @staticmethod
    def _metric_value_from_totals(metric_name, totals):
        for total_key, names in InfluenceHistoryService._METRIC_TOTAL_GROUPS.items():
            if metric_name in names:
                return _to_number(totals.get(total_key, 0))
        return 0

    @staticmethod
    def get_after_time(hour):
        return PageHistoryRepository.get_after_time(hour)

    @staticmethod
    def get_today_pages_history():
        return PageHistoryRepository().get_today_all()

    @staticmethod
    def get_page_history_today(page_id):
        return PageHistoryRepository().get_page_data_today(page_id)

    @staticmethod
    def get_platform_history(platform):
        return PageHistoryRepository().get_platform_history(platform)

    @staticmethod
    def get_entity_history(entity_id, date_str=None):
        target_date = parse_iso_date(date_str) if date_str else date.today()
        return PageHistoryRepository().get_entity_data_by_date(entity_id, target_date)

    @staticmethod
    def get_entities_ranking():
        return PageHistoryRepository.get_all_entities_ranking()

    @staticmethod
    def entities_ranking():
        start_date = datetime.now() - timedelta(days=30)
        data = PageHistoryRepository.get_all_entities_posts(date_limit=start_date)
        followers_snapshot = PageHistoryRepository.get_entities_followers_snapshot(date_limit=start_date)

        followers_by_page = {
            row.page_id: {
                "current": row.current_followers or 0,
                "prev": row.prev_followers or 0,
            }
            for row in followers_snapshot
        }

        structured_entities = defaultdict(lambda: {
            "platforms": {},
            "posts": [],
            "_platform_ts": {}
        })

        for row in data:
            entity = structured_entities[row.entity_id]

            entity["entity_id"] = row.entity_id
            entity["entity_name"] = row.entity_name
            entity["category"] = row.category
            entity["root_category"] = row.root_category

            prev_ts = entity["_platform_ts"].get(row.platform)
            if prev_ts is None or row.recorded_at > prev_ts:
                entity["_platform_ts"][row.platform] = row.recorded_at
                snap = followers_by_page.get(row.page_id, {"current": 0, "prev": 0})
                entity["platforms"][row.platform] = {
                    "followers": snap["current"],
                    "prev_followers": snap["prev"],
                    "page_id": row.page_id,
                    "page_name": row.page_name,
                    "profile_url": row.page_url,
                    "profile_image_url": row.profile_url,
                }

            if row.posts_metrics:
                entity["posts"].append({"platform": row.platform, "metrics": row.posts_metrics})

        entity_scores = []

        for entity_id, entity_data in structured_entities.items():
            total_score = 0
            total_posts = 0

            for post_block in entity_data["posts"]:
                platform = post_block["platform"]
                posts_metrics = post_block["metrics"]

                if platform not in platform_metrics:
                    continue

                metrics_def = platform_metrics[platform]["metrics"]

                for post in posts_metrics:
                    for m in metrics_def:
                        value = post.get(m["name"], 0) or 0
                        total_score += value * m["score"]
                    total_posts += 1

            total_followers = sum(p["followers"] for p in entity_data["platforms"].values())
            total_prev_followers = sum(p["prev_followers"] for p in entity_data["platforms"].values())

            entity_scores.append({
                "entity_id": entity_id,
                "entity_name": entity_data["entity_name"],
                "category": entity_data["category"],
                "root_category": entity_data["root_category"],
                "platforms": entity_data["platforms"],
                "total_score": total_score,
                "average_score": total_score / total_posts if total_posts else 0,
                "total_followers": total_followers,
                "total_prev_followers": total_prev_followers,
            })

        entity_scores.sort(key=lambda x: x["total_followers"], reverse=True)

        for idx, entity in enumerate(entity_scores, start=1):
            entity["rank"] = idx

        return entity_scores

    @staticmethod
    def get_interactions_ranking(start_date=None):
        date_limit = parse_iso_date(start_date) if start_date else (datetime.now() - timedelta(days=30)).date()
        rows = PageHistoryRepository.get_companies_interactions_summary(date_limit=date_limit)
        if not rows:
            return []

        entities = {}

        for row in rows:
            platform = InfluenceHistoryService._row_value(row, "platform", None)
            if platform not in platform_metrics:
                continue

            entity_id = InfluenceHistoryService._row_value(row, "entity_id", None)
            entity_name = InfluenceHistoryService._row_value(row, "entity_name", None)
            category = InfluenceHistoryService._row_value(row, "category", None)
            root_category = InfluenceHistoryService._row_value(row, "root_category", None)
            if entity_id is None:
                continue

            totals = {
                "likes": _to_number(InfluenceHistoryService._row_value(row, "total_likes", 0)),
                "comments": _to_number(InfluenceHistoryService._row_value(row, "total_comments", 0)),
                "shares": _to_number(InfluenceHistoryService._row_value(row, "total_shares", 0)),
                "views": _to_number(InfluenceHistoryService._row_value(row, "total_views", 0)),
            }
            posts_count = _to_number(InfluenceHistoryService._row_value(row, "posts_count", 0))
            page_id = InfluenceHistoryService._row_value(row, "page_id", None)
            page_name = InfluenceHistoryService._row_value(row, "page_name", None)
            page_url = InfluenceHistoryService._row_value(row, "page_url", None)
            profile_image_url = InfluenceHistoryService._row_value(row, "profile_image_url", None)

            metrics = platform_metrics.get(platform, {}).get("metrics", [])
            platform_score = 0.0
            for metric in metrics:
                metric_name = metric["name"]
                metric_weight = metric.get("score", 1.0)
                platform_score += InfluenceHistoryService._metric_value_from_totals(metric_name, totals) * metric_weight

            entity = entities.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "entity_name": entity_name,
                    "category": category,
                    "root_category": root_category,
                    "window_start": date_limit.isoformat(),
                    "total_score": 0.0,
                    "total_posts": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                    "total_shares": 0,
                    "total_views": 0,
                    "platforms": {},
                },
            )

            if entity.get("category") is None and category is not None:
                entity["category"] = category
            if entity.get("root_category") is None and root_category is not None:
                entity["root_category"] = root_category

            entity["total_score"] += platform_score
            entity["total_posts"] += posts_count
            entity["total_likes"] += totals["likes"]
            entity["total_comments"] += totals["comments"]
            entity["total_shares"] += totals["shares"]
            entity["total_views"] += totals["views"]
            entity["platforms"][platform] = {
                "page_name": page_name,
                "page_id": page_id,
                "page_url": page_url,
                "profile_image_url": profile_image_url,
                "posts_count": posts_count,
                "likes": totals["likes"],
                "comments": totals["comments"],
                "shares": totals["shares"],
                "views": totals["views"],
                "score": round(platform_score, 4),
            }

        ranking = list(entities.values())
        for row in ranking:
            row["total_score"] = round(row["total_score"], 4)

        ranking.sort(key=lambda x: x["total_score"], reverse=True)
        for idx, row in enumerate(ranking, start=1):
            row["rank"] = idx

        return ranking

    @staticmethod
    def get_entity_interaction_stats(entity_id, start_date=None):
        data = PageHistoryRepository.get_entity_posts__old(entity_id=entity_id)
        if not data:
            return []

        daily_posts = {}

        for row in data:
            platform = row.platform if hasattr(row, "platform") else row[2]
            posts = row.posts if hasattr(row, "posts") else row[4]
            recorded_at = row.recorded_at if hasattr(row, "recorded_at") else row[3]

            if platform not in platform_metrics:
                continue

            if not posts:
                continue
            if isinstance(posts, list) and len(posts) > 0 and isinstance(posts[0], list):
                posts = sum(posts, [])
            if not isinstance(posts, list):
                continue

            day_key = recorded_at.date().isoformat()
            if day_key not in daily_posts:
                daily_posts[day_key] = {}

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]
            date_key = platform_metrics[platform]["date"]

            for post in posts:
                if not isinstance(post, dict):
                    continue

                post_id = post.get(id_key)
                if not post_id:
                    continue

                post_date = post.get(date_key)
                if start_date and post_date and ensure_datetime(post_date) < start_date:
                    continue

                daily_posts[day_key][post_id] = {
                    "post_id": post_id,
                    "platform": platform,
                    "create_time": post_date,
                    **{m["name"]: post.get(m["name"], 0) for m in metrics},
                }

        sorted_days = sorted(daily_posts.keys())
        if not sorted_days:
            return []

        first_day = ensure_datetime(sorted_days[0]).date()
        last_day = ensure_datetime(sorted_days[-1]).date()
        all_days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]

        distributed_gains = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        post_series = defaultdict(list)
        for day_key, posts_map in daily_posts.items():
            day_date = ensure_datetime(day_key).date()
            for post_id, post_data in (posts_map or {}).items():
                platform = post_data.get("platform")
                post_series[(platform, post_id)].append((day_date, post_data))

        for (platform, _post_id), samples in post_series.items():
            metric_defs = platform_metrics.get(platform, {}).get("metrics", [])
            if not metric_defs:
                continue

            samples.sort(key=lambda x: x[0])

            for idx in range(1, len(samples)):
                prev_day, prev_data = samples[idx - 1]
                cur_day, cur_data = samples[idx]

                span_days = (cur_day - prev_day).days
                if span_days <= 0:
                    continue

                for metric in metric_defs:
                    metric_name = metric["name"]
                    prev_val = _to_number(prev_data.get(metric_name, 0))
                    cur_val = _to_number(cur_data.get(metric_name, 0))
                    step_gain = (cur_val - prev_val) / span_days

                    for step in range(1, span_days + 1):
                        day = prev_day + timedelta(days=step)
                        distributed_gains[day][platform][metric_name] += step_gain

        summary = []
        for day in all_days:
            day_platform_scores = {}
            day_gains = {}
            day_total_score = 0.0

            platforms_data = distributed_gains.get(day, {})
            for platform, metrics_map in platforms_data.items():
                metric_defs = platform_metrics.get(platform, {}).get("metrics", [])
                metric_weights = {m["name"]: m.get("score", 1.0) for m in metric_defs}

                platform_score = 0.0
                day_gains[platform] = {}

                for metric_name, metric_value in metrics_map.items():
                    value = float(metric_value)
                    day_gains[platform][metric_name] = value
                    platform_score += value * metric_weights.get(metric_name, 1.0)

                day_platform_scores[platform] = platform_score
                day_total_score += platform_score

            summary.append({
                "date": day.isoformat(),
                "total_score": day_total_score,
                "platform_scores": day_platform_scores,
                "day_gains": day_gains,
            })

        return summary

    @staticmethod
    def get_competitors_interaction_stats(entity_ids, start_date=None):
        normalized_start = ensure_datetime(start_date) if start_date else None
        date_limit = normalized_start.date() if normalized_start else date.today() - timedelta(days=30)

        data = []
        for entity_id in entity_ids:
            data.extend(
                PageHistoryRepository().get_entity_posts_new(
                    entity_id=entity_id,
                    date_limit=date_limit,
                    max_posts=10000,
                )
            )

        if not data:
            return []

        post_scores = []

        for row in data:
            platform = row.platform if hasattr(row, "platform") else row[2]
            page_id = row.page_id if hasattr(row, "page_id") else row[0]
            entity_id = row.entity_id if hasattr(row, "entity_id") else row[5]

            if platform not in platform_metrics:
                continue

            posts = row.posts_metrics if hasattr(row, "posts_metrics") else row[4]
            if not posts:
                continue
            if isinstance(posts, list) and len(posts) > 0 and isinstance(posts[0], list):
                posts = sum(posts, [])
            if not isinstance(posts, list):
                continue

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]

            for post in posts:
                if not isinstance(post, dict):
                    continue

                post_sc = 0

                post_date = post.get(platform_metrics[platform]["date"])
                if normalized_start and post_date and normalized_start > ensure_datetime(post_date):
                    continue

                for metric in metrics:
                    metric_name = metric["name"]
                    metric_score = metric["score"]

                    value = _to_number(post.get(metric_name, 0))
                    post_sc += value * metric_score

                post_scores.append({
                    "post_id": post.get(id_key),
                    **{m["name"]: post.get(m["name"], 0) for m in metrics},
                    "score": post_sc,
                    "platform": platform,
                    "create_time": post.get(platform_metrics[platform]["date"]),
                    "page_id": page_id,
                    "entity_id": entity_id,
                })

        return post_scores
