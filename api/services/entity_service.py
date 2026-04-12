from collections import defaultdict
from datetime import datetime, timezone, timedelta

from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.utils.data_keys import platform_metrics
from api.utils.logging_utils import instrument_service_class
from api.utils.request_parsing import parse_iso_date
from api.utils.posts_utils import _to_number, ensure_datetime, parse_relative_time


@instrument_service_class
class EntityService:
    @staticmethod
    def refine_daily_followers(points):
        if not points:
            return []

        by_day = {}
        for day, followers in points:
            by_day[day] = followers

        start_day = min(by_day.keys())
        end_day = max(by_day.keys())
        total_days = (end_day - start_day).days + 1

        days = [start_day + timedelta(days=i) for i in range(total_days)]
        values = [by_day.get(day) for day in days]

        def _is_missing(value):
            return value is None or value == 0

        i = 0
        n = len(values)
        while i < n:
            if not _is_missing(values[i]):
                i += 1
                continue

            run_start = i
            while i < n and _is_missing(values[i]):
                i += 1
            run_end = i - 1

            left_idx = run_start - 1
            right_idx = i if i < n else None

            left_val = values[left_idx] if left_idx >= 0 and not _is_missing(values[left_idx]) else None
            right_val = values[right_idx] if right_idx is not None and not _is_missing(values[right_idx]) else None

            if left_val is not None and right_val is not None:
                gap = right_idx - left_idx
                for k in range(run_start, run_end + 1):
                    ratio = (k - left_idx) / gap
                    interpolated = left_val + (right_val - left_val) * ratio
                    values[k] = max(0, int(round(interpolated)))
            elif left_val is not None:
                for k in range(run_start, run_end + 1):
                    values[k] = left_val
            elif right_val is not None:
                for k in range(run_start, run_end + 1):
                    values[k] = right_val
            else:
                for k in range(run_start, run_end + 1):
                    values[k] = 0

        return list(zip(days, values))

    @staticmethod
    def create_entity(name, entity_type, category_id):
        entity = EntityRepository.create(name=name, type_=entity_type)
        entity_category = EntityCategoryRepository.add(entity_id=entity.id, category_id=category_id)
        return entity, entity_category

    @staticmethod
    def get_all_entities():
        return EntityRepository.get_all()

    @staticmethod
    def get_existing_entities():
        return EntityRepository.get_who_has_history()

    @staticmethod
    def delete_entity(entity_id):
        EntityCategoryRepository.delete_by_entity(entity_id)
        return EntityRepository.delete(entity_id)

    @staticmethod
    def get_entity_profile_card(entity_id):
        return PageHistoryRepository.get_entity_info_from_history(entity_id)

    @staticmethod
    def get_entity_followers_history(entity_id):
        history = PageHistoryRepository().get_followers_history_by_entity(entity_id)
        if not history:
            return []

        grouped = defaultdict(list)
        for row in history:
            grouped[(row.page_id, row.platform)].append((row.recorded_at.date(), row.followers))

        data = []
        for (page_id, platform), points in grouped.items():
            refined_points = EntityService.refine_daily_followers(points)
            for day, followers in refined_points:
                data.append(
                    {
                        "page_id": page_id,
                        "followers": followers,
                        "date": day.isoformat(),
                        "platform": platform,
                    }
                )

        data.sort(key=lambda x: (x["date"], x["platform"], str(x["page_id"])))
        return data

    @staticmethod
    def compare_entities_followers(entity_ids):
        raw_results = PageHistoryRepository.get_entites_followers_competition(entity_ids)
        if not raw_results:
            return None

        data = defaultdict(lambda: {"entity_id": None, "records": []})
        grouped = defaultdict(list)

        for row in raw_results:
            if row.entity_name:
                if data[row.entity_name]["entity_id"] is None:
                    data[row.entity_name]["entity_id"] = row.entity_id
                grouped[(row.entity_name, row.platform)].append((row.recorded_at.date(), row.followers))

        for (entity_name, platform), points in grouped.items():
            refined_points = EntityService.refine_daily_followers(points)
            for day, followers in refined_points:
                data[entity_name]["records"].append(
                    {
                        "date": day.isoformat(),
                        "platform": platform,
                        "followers": followers,
                    }
                )

        for entity_name in data:
            data[entity_name]["records"].sort(key=lambda x: (x["date"], x["platform"]))
        return data

    @staticmethod
    def _build_likes_gains_rows(rows):
        likes_metric_key = {
            "instagram": "likes",
            "linkedin": "likes_count",
            "tiktok": "favorites_count",
            "x": "likes",
            "facebook": "likes",
        }
        id_key = {
            "instagram": platform_metrics["instagram"]["id_key"],
            "linkedin": platform_metrics["linkedin"]["id_key"],
            "tiktok": platform_metrics["tiktok"]["id_key"],
            "x": platform_metrics["x"]["id_key"],
            "facebook": platform_metrics["facebook"]["id_key"],
        }
        return EntityService._build_metric_gains_rows(
            rows,
            metric_key_by_platform=likes_metric_key,
            id_key_by_platform=id_key,
            output_key="likes_gained",
        )

    @staticmethod
    def _build_comments_gains_rows(rows):
        comments_metric_key = {
            "instagram": "comments",
            "linkedin": "comments_count",
            "tiktok": "commentcount",
            "x": "replies",
            "facebook": "num_comments",
        }
        id_key = {
            "instagram": platform_metrics["instagram"]["id_key"],
            "linkedin": platform_metrics["linkedin"]["id_key"],
            "tiktok": platform_metrics["tiktok"]["id_key"],
            "x": platform_metrics["x"]["id_key"],
            "facebook": platform_metrics["facebook"]["id_key"],
        }
        return EntityService._build_metric_gains_rows(
            rows,
            metric_key_by_platform=comments_metric_key,
            id_key_by_platform=id_key,
            output_key="comments_gained",
        )

    @staticmethod
    def _build_metric_gains_rows(rows, metric_key_by_platform, id_key_by_platform, output_key):
        if not rows:
            return []

        # Per page/platform, keep one likes snapshot per post for each recorded day.
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
            if not day_posts:
                continue

            sorted_days = sorted(day_posts.keys())
            first_day = sorted_days[0]
            last_day = sorted_days[-1]

            post_series = defaultdict(list)
            for day in sorted_days:
                for post_id, likes_value in day_posts[day].items():
                    post_series[post_id].append((day, likes_value))

            distributed_gains = defaultdict(float)
            for samples in post_series.values():
                samples.sort(key=lambda x: x[0])

                for idx in range(1, len(samples)):
                    prev_day, prev_data = samples[idx - 1]
                    cur_day, cur_data = samples[idx]

                    span_days = (cur_day - prev_day).days
                    if span_days <= 0:
                        continue

                    step_gain = (cur_data - prev_data) / span_days
                    for step in range(1, span_days + 1):
                        day = prev_day + timedelta(days=step)
                        distributed_gains[day] += step_gain

            day_range = (last_day - first_day).days + 1
            for i in range(day_range):
                day = first_day + timedelta(days=i)
                metric_gained = round(distributed_gains.get(day, 0.0), 4)
                if float(metric_gained).is_integer():
                    metric_gained = int(metric_gained)

                data.append(
                    {
                        "page_id": page_id,
                        "platform": platform,
                        "date": day.isoformat(),
                        output_key: metric_gained,
                    }
                )

        data.sort(key=lambda x: (x["date"], x["platform"], str(x["page_id"])))
        return data

    @staticmethod
    def get_entity_likes_history(entity_id, start_date=None):
        date_limit = parse_iso_date(start_date) if start_date else datetime.now(timezone.utc).date() - timedelta(days=30)
        history = PageHistoryRepository().get_entity_likes_development(entity_id, date_limit=date_limit)
        if not history:
            return []

        return EntityService._build_likes_gains_rows(history)

    @staticmethod
    def compare_entities_likes(entity_ids, start_date=None):
        date_limit = parse_iso_date(start_date) if start_date else datetime.now(timezone.utc).date() - timedelta(days=30)
        raw_results = PageHistoryRepository().get_entities_likes_development(entity_ids, date_limit=date_limit)
        if not raw_results:
            return None

        rows_by_entity = defaultdict(list)
        entity_ids_by_name = {}

        for row in raw_results:
            if not row.entity_name:
                continue
            rows_by_entity[row.entity_name].append(row)
            entity_ids_by_name[row.entity_name] = row.entity_id

        if not rows_by_entity:
            return None

        data = {}
        for entity_name, rows in rows_by_entity.items():
            records = EntityService._build_likes_gains_rows(rows)
            if not records:
                continue

            data[entity_name] = {
                "entity_id": entity_ids_by_name.get(entity_name),
                "records": records,
            }

        if not data:
            return None

        return data

    @staticmethod
    def get_entity_comments_history(entity_id, start_date=None):
        date_limit = parse_iso_date(start_date) if start_date else datetime.now(timezone.utc).date() - timedelta(days=30)
        history = PageHistoryRepository().get_entity_comments_development(entity_id, date_limit=date_limit)
        if not history:
            return []

        return EntityService._build_comments_gains_rows(history)

    @staticmethod
    def compare_entities_comments(entity_ids, start_date=None):
        date_limit = parse_iso_date(start_date) if start_date else datetime.now(timezone.utc).date() - timedelta(days=30)
        raw_results = PageHistoryRepository().get_entities_comments_development(entity_ids, date_limit=date_limit)
        if not raw_results:
            return None

        rows_by_entity = defaultdict(list)
        entity_ids_by_name = {}

        for row in raw_results:
            if not row.entity_name:
                continue
            rows_by_entity[row.entity_name].append(row)
            entity_ids_by_name[row.entity_name] = row.entity_id

        if not rows_by_entity:
            return None

        data = {}
        for entity_name, rows in rows_by_entity.items():
            records = EntityService._build_comments_gains_rows(rows)
            if not records:
                continue

            data[entity_name] = {
                "entity_id": entity_ids_by_name.get(entity_name),
                "records": records,
            }

        if not data:
            return None

        return data

    @staticmethod
    def get_entity_posts_timeline(entity_id, date_str=None, max_posts=None):
        if date_str:
            date = parse_iso_date(date_str)
        else:
            date = ensure_datetime(datetime.now(timezone.utc)).date() - timedelta(days=30)

        if max_posts is None or max_posts <= 0:
            max_posts = 10000

        history = PageHistoryRepository().get_entity_posts_new(entity_id, date_limit=date, max_posts=max_posts)
        if not history:
            return []

        sorting_map = {
            "instagram": "datetime",
            "linkedin": "date",
            "tiktok": "create_date",
            "youtube": "posted_time",
            "x": None,
        }

        filter_date = None
        if date_str:
            filter_date = ensure_datetime(date_str)
            if filter_date.tzinfo is None:
                filter_date = filter_date.replace(tzinfo=timezone.utc)
            else:
                filter_date = filter_date.astimezone(timezone.utc)

        all_posts = []
        for row in history:
            platform = row.platform
            page_id = row.page_id
            page_name = row.page_name
            posts_metrics = row.posts_metrics

            if not posts_metrics or len(posts_metrics) == 0:
                continue

            for post in posts_metrics:
                sort_key = sorting_map.get(platform)
                if not sort_key:
                    continue

                raw_date = post.get(sort_key)
                if not raw_date:
                    continue

                if platform == "youtube":
                    raw_date = parse_relative_time(raw_date)
                    if not raw_date:
                        continue

                post_date = ensure_datetime(raw_date)
                post["compare_date"] = post_date
                post["platform"] = platform
                post["page_id"] = page_id
                post["page_name"] = page_name

                if filter_date and post_date < filter_date:
                    continue

                all_posts.append(post)

        all_posts.sort(key=lambda x: x["compare_date"], reverse=True)
        if max_posts and all_posts:
            all_posts = all_posts[:max_posts]

        return all_posts

    @staticmethod
    def mark_entity_to_scrape(entity_id):
        return EntityRepository.change_to_scrape(entity_id, True)

    @staticmethod
    def get_entity_top_posts(entity_id, date_value=None, top_posts=5):
        date = parse_iso_date(date_value) if date_value else datetime.now(timezone.utc).date()
        date_limit = date - timedelta(days=10)

        data = EntityRepository.get_entity_posts_metrics(entity_id, date_limit)

        skipped = 0
        posts_num = 0

        daily_posts = {}
        for post in data:
            platform = post.platform if hasattr(post, "platform") else post[2]
            posts = post.posts_metrics if hasattr(post, "posts_metrics") else post[4]
            recorded_at = post.recorded_at if hasattr(post, "recorded_at") else post[3]

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

            for p in posts:
                posts_num += 1
                if not isinstance(p, dict):
                    skipped += 1
                    continue

                post_id = p.get(id_key)
                if not post_id:
                    skipped += 1
                    continue

                post_date = p.get(date_key)
                if date_limit and post_date and ensure_datetime(post_date).date() < date_limit:
                    skipped += 1
                    continue

                daily_posts[day_key][post_id] = {
                    "post_id": post_id,
                    "platform": platform,
                    "create_time": post_date,
                    **{m["name"]: p.get(m["name"], 0) for m in metrics},
                    **p,
                }

        sorted_days = sorted(daily_posts.keys())
        final_output = []

        for i, day in enumerate(sorted_days):
            current_day_posts = daily_posts[day] or {}
            previous_day_posts = {}
            j = i - 1
            while j >= 0:
                candidate = daily_posts.get(sorted_days[j], {})
                if candidate and candidate != {}:
                    previous_day_posts = candidate
                    break
                j -= 1

            day_output = {"day": day, "posts": []}

            for post_id, post_data in current_day_posts.items():
                platform = post_data.get("platform")
                metrics = platform_metrics.get(platform, {}).get("metrics", [])

                previous_post = previous_day_posts.get(post_id, {})

                gains = {}
                if previous_post and previous_post != {}:
                    for m in metrics:
                        name = m["name"]
                        cur_val = _to_number(post_data.get(name, 0))
                        prev_val = _to_number(previous_post.get(name, 0))

                        gains[f"gained_{name}"] = cur_val - prev_val

                    day_output["posts"].append({**post_data, **gains})

            final_output.append(day_output)

        day_gains = next((item for item in final_output if item["day"] == str(date)), None)
        if day_gains:
            for post in day_gains["posts"]:
                score = sum(
                    post.get(f"gained_{m['name']}", 0) * m.get("weight", 1)
                    for m in platform_metrics.get(post.get("platform"), {}).get("metrics", [])
                )
                post["total_score"] = score

            day_gains["posts"].sort(key=lambda x: x["total_score"], reverse=True)

            for rank, post in enumerate(day_gains["posts"], start=1):
                post["rank"] = rank

            day_gains["posts"] = day_gains["posts"][:top_posts]

        return day_gains, posts_num, skipped