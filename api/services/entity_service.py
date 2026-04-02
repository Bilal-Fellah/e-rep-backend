from collections import defaultdict
from datetime import datetime, timezone, timedelta

from api.repositories.entity_category_repository import EntityCategoryRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.utils.data_keys import platform_metrics
from api.utils.request_parsing import parse_iso_date
from api.utils.posts_utils import _to_number, ensure_datetime, parse_relative_time


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
                raw_date = None
                if sorting_map[platform] in post:
                    raw_date = post[sorting_map[platform]] if sorting_map[platform] else None
                if not raw_date:
                    continue

                if platform == "youtube":
                    raw_date = parse_relative_time(raw_date)

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