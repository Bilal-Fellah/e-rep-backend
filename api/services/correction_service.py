# Business logic for the admin "data correction" workflow.
#
# Why this exists: posts_mv/posts_history_mv are read-only materialized
# views derived from pages_history, and most other tables are populated by
# the scraper — there's no generic "edit any cell" UI for this data, on
# purpose. But scraped data is sometimes missing or wrong (a null follower
# count, a garbled bio, a mistyped entity name) and someone needs a safe,
# audited way to fix it without shelling into Postgres.
#
# This is deliberately NOT a general-purpose table editor. It only allows
# a small, explicit whitelist of (target_type, field) pairs — the ones
# that are plain scalar columns or top-level JSON keys, cheap to validate,
# and safe to overwrite. Every write is wrapped in a single DB transaction
# together with its audit row, so a correction and its audit trail can
# never diverge: either both are committed or neither is.
from api import db
from api.repositories.data_correction_repository import DataCorrectionRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.page_repository import PageRepository
from api.repositories.post_repository import PostRepository
from api.utils.logging_utils import instrument_service_class

# How each platform stores its posts inside a pages_history snapshot's
# `data` JSONB — see api/database/posts_mv_queries.sql, which this table
# mirrors. `flat: True` (Facebook) means the pages_history row itself IS
# the post, rather than one element of an array.
POST_METRIC_PLATFORM_MAP = {
    "instagram": {"array_key": "posts", "id_key": "id", "metrics": {"likes": "likes", "comments": "comments"}},
    "linkedin": {"array_key": "updates", "id_key": "post_id", "metrics": {"likes": "likes_count", "comments": "comments_count"}},
    "tiktok": {
        "array_key": "top_videos",
        "id_key": "video_id",
        "metrics": {"likes": "favorites_count", "comments": "commentcount", "shares": "share_count"},
    },
    "youtube": {"array_key": "top_videos", "id_key": "video_id", "metrics": {"likes": "like_count", "comments": "comment_count"}},
    "x": {"array_key": "posts", "id_key": "post_id", "metrics": {"likes": "likes", "comments": "replies", "shares": "reposts"}},
    "facebook": {"flat": True, "metrics": {"likes": "likes", "comments": "num_comments", "shares": "num_shares"}},
}

# Whitelist of what can be corrected, and how to read/coerce/write each field.
# Adding a new correctable field means adding one entry here — nothing else
# should ever bypass this table to write to these rows.
CORRECTABLE_FIELDS = {
    "entity": {
        "name": {"type": str, "label": "Name"},
        "type": {
            "type": str,
            "label": "Type",
            "choices": ("company", "influencer", "small-business"),
        },
    },
    "page": {
        "name": {"type": str, "label": "Name"},
        "link": {"type": str, "label": "Link"},
    },
    # `page_history` corrects one top-level scraped field on one historical
    # snapshot (e.g. "followers", "biography", "page_followers",
    # "subscribers", "profile_image_link" — whatever key the scraper for
    # that platform uses). Nested arrays (posts/updates/top_videos) are out
    # of scope for this quick-fix path.
    "page_history": {
        "followers": {"type": int, "label": "Followers"},
        "page_followers": {"type": int, "label": "Page followers (Facebook)"},
        "subscribers": {"type": int, "label": "Subscribers (YouTube)"},
        "biography": {"type": str, "label": "Biography"},
        "about": {"type": str, "label": "About (LinkedIn)"},
        "Description": {"type": str, "label": "Description (YouTube)"},
        "profile_image_link": {"type": str, "label": "Profile image URL"},
        "profile_image": {"type": str, "label": "Profile image URL (YouTube)"},
        "profile_pic_url": {"type": str, "label": "Profile image URL (TikTok)"},
        "logo": {"type": str, "label": "Logo URL (LinkedIn)"},
    },
    # `post_metric` corrects one engagement number on one specific post,
    # from one specific historical snapshot ("day"). target_id is a
    # composite "<pages_history.id>:<post_id>" — see _apply_post_metric.
    # Whether `shares` applies is platform-specific (not every platform
    # tracks it) and can only be checked once the target row is loaded, so
    # it's validated at apply time rather than restricted here.
    "post_metric": {
        "likes": {"type": int, "label": "Likes"},
        "comments": {"type": int, "label": "Comments"},
        "shares": {"type": int, "label": "Shares"},
    },
}


class CorrectionError(ValueError):
    """Raised for any invalid correction request; carries a user-facing message."""


def _coerce(raw_value, field_type):
    if raw_value is None:
        return None
    if field_type is int:
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise CorrectionError("Value must be a whole number.")
    return str(raw_value)


@instrument_service_class
class CorrectionService:
    @staticmethod
    def list_targets():
        """Describe the whitelist for the admin UI to render a form from."""
        return {
            target_type: [
                {"field": field, "label": spec["label"], "choices": spec.get("choices")}
                for field, spec in fields.items()
            ]
            for target_type, fields in CORRECTABLE_FIELDS.items()
        }

    @staticmethod
    def valid_target_types():
        """The whitelist's target_type keys — the single source of truth
        for validating a `target_type` query/body param anywhere in the
        routes layer, so it can never drift from CORRECTABLE_FIELDS."""
        return list(CORRECTABLE_FIELDS.keys())

    @staticmethod
    def list_corrections(target_type=None, limit=50, offset=0):
        rows, total = DataCorrectionRepository.list_all(target_type=target_type, limit=limit, offset=offset)
        return rows, total

    @staticmethod
    def apply_correction(target_type, target_id, field, new_value, reason, admin_user_id):
        if not reason or not str(reason).strip():
            raise CorrectionError("A reason is required for every correction.")

        fields = CORRECTABLE_FIELDS.get(target_type)
        if fields is None:
            raise CorrectionError(
                f"target_type must be one of {list(CORRECTABLE_FIELDS.keys())}."
            )
        spec = fields.get(field)
        if spec is None:
            raise CorrectionError(
                f"'{field}' is not a correctable field for '{target_type}'. "
                f"Allowed: {list(fields.keys())}."
            )

        # Coerce first, then validate against `choices` — comparing the raw
        # (pre-coercion) request value would silently pass the wrong
        # representation for any future non-str choices field.
        value = _coerce(new_value, spec["type"])

        choices = spec.get("choices")
        if choices and value not in choices:
            raise CorrectionError(f"'{field}' must be one of {list(choices)}.")

        try:
            if target_type == "entity":
                old_value, row = CorrectionService._apply_entity(target_id, field, value)
            elif target_type == "page":
                old_value, row = CorrectionService._apply_page(target_id, field, value)
            elif target_type == "post_metric":
                old_value, row = CorrectionService._apply_post_metric(target_id, field, value)
            elif target_type == "page_history":
                old_value, row = CorrectionService._apply_page_history(target_id, field, value)
            else:
                # Unreachable today — target_type was already checked against
                # CORRECTABLE_FIELDS above — but explicit here rather than a
                # bare `else` that would silently route a future new
                # target_type into _apply_page_history.
                raise CorrectionError(f"No dispatch implemented for target_type '{target_type}'.")

            if row is None:
                raise CorrectionError(f"No {target_type} found with id '{target_id}'.")

            audit = DataCorrectionRepository.create(
                target_type=target_type,
                target_id=target_id,
                field=field,
                old_value=None if old_value is None else str(old_value),
                new_value=None if value is None else str(value),
                reason=str(reason).strip(),
                admin_user_id=admin_user_id,
                commit=False,
            )
            db.session.commit()
        except CorrectionError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise

        if target_type == "post_metric":
            # Best-effort, after the write already committed — see
            # PostRepository.refresh_post_views().
            PostRepository.refresh_post_views()

        return audit, row

    @staticmethod
    def _apply_entity(entity_id, field, value):
        entity = EntityRepository.get_by_id(entity_id)
        if not entity:
            return None, None
        old_value = getattr(entity, field)
        EntityRepository.update(entity_id, commit=False, **{field: value})
        return old_value, entity

    @staticmethod
    def _apply_page(page_id, field, value):
        # Not routed through PageRepository.update() — that helper commits
        # immediately, which would break the single-transaction guarantee
        # this service relies on (write + audit row must commit together).
        page = PageRepository.get_by_id(page_id)
        if not page:
            return None, None
        old_value = getattr(page, field)
        setattr(page, field, value)
        db.session.flush()
        return old_value, page

    @staticmethod
    def _apply_post_metric(target_id, field, value):
        if not isinstance(target_id, str) or ":" not in target_id:
            raise CorrectionError(
                "post_metric target_id must be \"<pages_history_id>:<post_id>\", e.g. '482:DGx123'."
            )
        history_id_raw, post_id = target_id.split(":", 1)
        try:
            history_id = int(history_id_raw)
        except ValueError:
            raise CorrectionError("The pages_history_id half of target_id must be an integer.")
        if not post_id:
            raise CorrectionError("post_metric target_id is missing the post_id half.")

        history = PageHistoryRepository.get_by_id(history_id)
        if not history:
            return None, None

        page = PageRepository.get_by_id(history.page_id)
        if not page:
            # Data-integrity edge case, not a user input error: the
            # snapshot exists but its page doesn't (e.g. deleted since).
            raise CorrectionError(f"pages_history #{history_id} has no owning page; cannot resolve its platform.")

        platform_spec = POST_METRIC_PLATFORM_MAP.get(page.platform)
        if platform_spec is None:
            raise CorrectionError(f"Post metrics aren't supported for platform '{page.platform}'.")

        metric_key = platform_spec["metrics"].get(field)
        if metric_key is None:
            raise CorrectionError(
                f"'{page.platform}' posts don't track '{field}'. "
                f"Supported here: {list(platform_spec['metrics'].keys())}."
            )

        if platform_spec.get("flat"):
            # Facebook: the pages_history row itself is the post — sanity
            # check the caller has the right row before patching it.
            data_post_id = (history.data or {}).get("post_id")
            if data_post_id is not None and str(data_post_id) != str(post_id):
                raise CorrectionError(
                    f"pages_history #{history_id} is post '{data_post_id}', not '{post_id}'."
                )
            old_value = (history.data or {}).get(metric_key)
            PageHistoryRepository.update_data_field(history_id, metric_key, value, commit=False)
            return old_value, history

        history, found, old_value = PageHistoryRepository.update_post_metric_in_array(
            history_id,
            platform_spec["array_key"],
            platform_spec["id_key"],
            post_id,
            metric_key,
            value,
            commit=False,
        )
        if not found:
            raise CorrectionError(
                f"No post '{post_id}' found in pages_history #{history_id}'s '{platform_spec['array_key']}'."
            )
        return old_value, history

    @staticmethod
    def _apply_page_history(history_id, field, value):
        try:
            history_id = int(history_id)
        except (TypeError, ValueError):
            raise CorrectionError("page_history target_id must be an integer id.")
        history = PageHistoryRepository.get_by_id(history_id)
        if not history:
            return None, None
        old_value = (history.data or {}).get(field)
        PageHistoryRepository.update_data_field(history_id, field, value, commit=False)
        return old_value, history
