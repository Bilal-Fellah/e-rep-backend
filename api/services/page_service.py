from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.page_repository import PageRepository
from api.utils.data_keys import platform_metrics
from api.utils.logging_utils import instrument_service_class
from api.utils.page_uuid import create_page_uuid
from api.utils.posts_utils import ensure_datetime
from api.utils.request_parsing import parse_iso_date


@instrument_service_class
class PageService:
    @staticmethod
    def create_page(data):
        platform = data.get("platform", "").strip().lower()
        link = data.get("link", "").strip().lower()
        entity_id = data.get("entity_id")

        if not platform or not link or not entity_id:
            return None, "Missing required fields: 'platform', 'link', or 'entity_id'."

        new_uuid = create_page_uuid(link)
        page = PageRepository.create(
            uuid=new_uuid,
            name=data.get("name", "").strip() or link,
            platform=platform,
            link=link,
            entity_id=entity_id,
        )
        return page, None

    @staticmethod
    def delete_page(page_id):
        return PageRepository.delete(page_id)

    @staticmethod
    def get_all_pages():
        return PageRepository.get_all()

    @staticmethod
    def get_pages_by_platform(platform):
        return PageRepository.get_by_platform(platform)

    @staticmethod
    def get_page_interaction_stats(page_id, start_date=None):
        start_datetime = None
        if start_date:
            parsed_start = parse_iso_date(start_date)
            if parsed_start:
                # Parse as start-of-day UTC to compare consistently with post datetimes.
                start_datetime = ensure_datetime(parsed_start.isoformat())

        data = PageHistoryRepository.get_page_posts(page_id=page_id)
        if not data:
            return []

        post_scores = []

        for row in data:
            platform = row[2]

            if platform not in platform_metrics:
                continue

            posts = row[4]
            if isinstance(posts, list) and len(posts) > 0:
                posts = posts[0]
            else:
                continue

            id_key = platform_metrics[platform]["id_key"]
            metrics = platform_metrics[platform]["metrics"]

            for post in posts:
                post_sc = 0

                post_date = post.get(platform_metrics[platform]["date"])
                if not post_date:
                    continue

                if start_datetime and start_datetime > ensure_datetime(post_date):
                    continue

                for metric in metrics:
                    metric_name = metric["name"]
                    metric_score = metric["score"]

                    value = post.get(metric_name, 0)
                    post_sc += value * metric_score

                post_scores.append(
                    {
                        "post_id": post.get(id_key),
                        **{metric["name"]: post.get(metric["name"], 0) for metric in metrics},
                        "score": post_sc,
                        "platform": platform,
                        "create_time": post.get(platform_metrics[platform]["date"]),
                    }
                )

        return post_scores