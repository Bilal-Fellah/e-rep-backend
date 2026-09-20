# Business logic for the admin "Priority" page -- the short list of paying
# clients that get a stricter standard of care than the rest of the
# database.
#
# Three things live here:
#
#   1. Membership of the list (add/remove/annotate an entity).
#   2. A deeper validity check than the fleet-wide Data Integrity report:
#      that report answers "how much data is missing overall, by platform";
#      this one answers "is *this client's* data actually complete right
#      now", page by page -- freshness, snapshot gaps over the last N days,
#      the structural check already used to flag failed scrapes, and the
#      posts-side null rates.
#   3. Firing a scrape for one client and then verifying it actually
#      landed. Worth being explicit about the shape of that: no scraper on
#      the VPS can target a single entity today -- a run is per (platform,
#      mode) and covers every active page on that platform. So "run it for
#      this client" queues the ordinary platform-wide run, tags the request
#      with the entity it was fired for, and verification then asks the
#      only question that actually matters to the client: did *their*
#      pages get new rows after the moment the run was queued.
from datetime import datetime, timedelta, timezone

from api.repositories.entity_repository import EntityRepository
from api.repositories.page_history_repository import PageHistoryRepository
from api.repositories.priority_entity_repository import PriorityEntityRepository
from api.services.scrape_trigger_service import (
    TRIGGERABLE,
    ScrapeTriggerError,
    ScrapeTriggerService,
)
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class

# A daily scrape that hasn't landed in this long is late but not yet an
# outage (timers drift, a long queue behind the shared scraper lock).
FRESH_HOURS = 30
# Past this, a page has missed a full cycle -- for a paying client that's
# not "late", it's broken.
STALE_HOURS = 54

# Default window for the gap check: how many of the last N days actually
# produced a snapshot for each page.
DEFAULT_CHECK_DAYS = 7

MAX_LABEL_LENGTH = 80

# Worst-wins ordering for rolling page statuses up to an entity.
_STATUS_RANK = {"ok": 0, "warning": 1, "critical": 2}


class PriorityEntityError(ValueError):
    """Raised for an unknown entity, a duplicate, or an untriggerable
    platform on this surface."""


def _worst(statuses) -> str:
    worst = "ok"
    for status in statuses:
        if _STATUS_RANK.get(status, 0) > _STATUS_RANK[worst]:
            worst = status
    return worst


def _hours_since(moment: datetime | None) -> float | None:
    if moment is None:
        return None
    # pages_history.recorded_at is timezone-aware in Postgres but naive
    # under the SQLite test DB -- treat a naive timestamp as UTC rather
    # than crashing on the subtraction.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - moment
    return round(delta.total_seconds() / 3600, 1)


@instrument_service_class
class PriorityEntityService:
    # ── Membership ────────────────────────────────────────────────────────

    @staticmethod
    def add(entity_id: int, label: str | None = None, note: str | None = None,
            added_by: int | None = None) -> dict:
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise PriorityEntityError(f"No entity with id {entity_id}.")
        if PriorityEntityRepository.get_by_entity_id(entity_id) is not None:
            raise PriorityEntityError(f"'{entity.name}' is already on the priority list.")

        label = (label or "").strip() or None
        if label and len(label) > MAX_LABEL_LENGTH:
            raise PriorityEntityError(f"label must be at most {MAX_LABEL_LENGTH} characters.")

        row = PriorityEntityRepository.create(
            entity_id=entity_id, label=label, note=(note or "").strip() or None, added_by=added_by
        )
        return {
            "id": row.id,
            "entity_id": row.entity_id,
            "entity_name": entity.name,
            "entity_type": entity.type,
            "label": row.label,
            "note": row.note,
            "created_at": iso_utc(row.created_at),
        }

    @staticmethod
    def update(entity_id: int, label: str | None = None, note: str | None = None) -> dict:
        row = PriorityEntityRepository.get_by_entity_id(entity_id)
        if row is None:
            raise PriorityEntityError(f"Entity {entity_id} isn't on the priority list.")
        if label is not None and len(label.strip()) > MAX_LABEL_LENGTH:
            raise PriorityEntityError(f"label must be at most {MAX_LABEL_LENGTH} characters.")

        # Empty string is a deliberate clear, not "leave unchanged" -- the
        # repository's update() skips None, so normalise before handing off.
        updates = {}
        if label is not None:
            updates["label"] = label.strip() or ""
        if note is not None:
            updates["note"] = note.strip() or ""
        for key, value in updates.items():
            setattr(row, key, value or None)
        PriorityEntityRepository.update(row)
        return {
            "entity_id": row.entity_id,
            "label": row.label,
            "note": row.note,
        }

    @staticmethod
    def remove(entity_id: int) -> dict:
        row = PriorityEntityRepository.get_by_entity_id(entity_id)
        if row is None:
            raise PriorityEntityError(f"Entity {entity_id} isn't on the priority list.")
        PriorityEntityRepository.delete(row)
        return {"removed_entity_id": entity_id}

    # ── The check ─────────────────────────────────────────────────────────

    @staticmethod
    def list_with_health(days: int = DEFAULT_CHECK_DAYS) -> list[dict]:
        """Every priority entity with its pages' health rolled up. Same
        per-page checks as check_entity(), batched across the whole list so
        the page loads in a fixed number of queries."""
        members = PriorityEntityRepository.list_all()
        if not members:
            return []

        entity_ids = [m.entity_id for m in members]
        pages_by_entity = PriorityEntityService._page_reports(entity_ids, days)

        out = []
        for member in members:
            pages = pages_by_entity.get(member.entity_id, [])
            out.append(
                {
                    "id": member.id,
                    "entity_id": member.entity_id,
                    "entity_name": member.entity_name,
                    "entity_type": member.entity_type,
                    "to_scrape": bool(member.to_scrape),
                    "label": member.label,
                    "note": member.note,
                    "created_at": iso_utc(member.created_at),
                    **PriorityEntityService._rollup(pages, bool(member.to_scrape)),
                }
            )
        return out

    @staticmethod
    def check_entity(entity_id: int, days: int = DEFAULT_CHECK_DAYS) -> dict:
        """The full per-page report for one client, plus its recent manual
        runs. Works whether or not the entity is on the priority list --
        the list decides what's watched, not what's checkable."""
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise PriorityEntityError(f"No entity with id {entity_id}.")

        member = PriorityEntityRepository.get_by_entity_id(entity_id)
        pages = PriorityEntityService._page_reports([entity_id], days).get(entity_id, [])

        return {
            "entity_id": entity.id,
            "entity_name": entity.name,
            "entity_type": entity.type,
            "to_scrape": bool(entity.to_scrape),
            "on_priority_list": member is not None,
            "label": getattr(member, "label", None),
            "note": getattr(member, "note", None),
            "days": days,
            "checked_at": iso_utc(datetime.now(timezone.utc)),
            "pages": pages,
            "triggerable": PriorityEntityService._triggerable_for(pages),
            "recent_runs": ScrapeTriggerService.list_for_entity(entity_id, limit=10),
            **PriorityEntityService._rollup(pages, bool(entity.to_scrape)),
        }

    @staticmethod
    def _rollup(pages: list[dict], to_scrape: bool) -> dict:
        """Entity-level verdict: the worst of its pages, with the entity's
        own blockers folded in. A paying client with to_scrape off, or with
        no pages at all, is critical no matter what the page rows say --
        both mean nothing will ever be collected for them."""
        issues = []
        statuses = [p["status"] for p in pages]

        if not pages:
            issues.append("No pages tracked for this entity")
            statuses.append("critical")
        if not to_scrape:
            issues.append("Entity is flagged to_scrape=false -- it is skipped by every scraper")
            statuses.append("critical")

        for page in pages:
            for reason in page["issues"]:
                issues.append(f"{page['platform']}: {reason}")

        return {
            "status": _worst(statuses),
            "pages_total": len(pages),
            "pages_ok": sum(1 for s in [p["status"] for p in pages] if s == "ok"),
            "pages_warning": sum(1 for s in [p["status"] for p in pages] if s == "warning"),
            "pages_critical": sum(1 for s in [p["status"] for p in pages] if s == "critical"),
            "issues": issues,
            "last_data_at": max(
                (p["last_snapshot_at"] for p in pages if p["last_snapshot_at"]), default=None
            ),
        }

    @staticmethod
    def _triggerable_for(pages: list[dict]) -> list[dict]:
        """Which (platform, mode) runs are worth offering for this client:
        the intersection of the platforms it actually has pages on and the
        own-scraper allowlist. Sorted so the UI order is stable."""
        platforms = {p["platform"] for p in pages}
        return [
            {"platform": platform, "mode": mode}
            for platform, mode in sorted(TRIGGERABLE)
            if platform in platforms
        ]

    @staticmethod
    def _page_reports(entity_ids: list[int], days: int) -> dict[int, list[dict]]:
        """Batched per-page health for a set of entities. One query each for
        pages, latest snapshots, snapshot counts and post stats."""
        pages = PriorityEntityRepository.get_pages_for_entities(entity_ids)
        if not pages:
            return {}

        page_ids = [p.uuid for p in pages]
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Latest snapshot per page. A tie on recorded_at can return two rows
        # for one page (nothing enforces uniqueness there) -- keep the
        # highest id, which is the last one written.
        latest_by_page: dict[str, object] = {}
        for row in PriorityEntityRepository.get_latest_history_for_pages(page_ids):
            key = str(row.page_id)
            current = latest_by_page.get(key)
            if current is None or row.id > current.id:
                latest_by_page[key] = row

        counts_by_page = {
            str(row.page_id): row
            for row in PriorityEntityRepository.count_history_since(page_ids, since)
        }
        posts_by_page = {
            str(row.page_id): row
            for row in PriorityEntityRepository.get_post_stats_for_pages(page_ids)
        }

        reports: dict[int, list[dict]] = {}
        for page in pages:
            key = str(page.uuid)
            reports.setdefault(page.entity_id, []).append(
                PriorityEntityService._page_report(
                    page=page,
                    latest=latest_by_page.get(key),
                    counts=counts_by_page.get(key),
                    posts=posts_by_page.get(key),
                    days=days,
                )
            )
        return reports

    @staticmethod
    def _page_report(page, latest, counts, posts, days: int) -> dict:
        issues: list[str] = []
        statuses: list[str] = []

        age_hours = _hours_since(getattr(latest, "recorded_at", None))
        missing_keys: list[str] = []

        if latest is None:
            issues.append("Never scraped -- no snapshot has ever been recorded")
            statuses.append("critical")
        else:
            # Same structural check the retry pipeline uses to decide a
            # scrape failed, applied to this page's newest snapshot.
            missing_keys = PageHistoryRepository.validate_data_structure(latest.data, page.platform)
            if missing_keys:
                # Everything missing means the snapshot is empty, not partial.
                empty = "followers" in missing_keys and any(
                    k.startswith(("posts", "updates", "top_videos")) for k in missing_keys
                )
                issues.append(f"Latest snapshot missing: {', '.join(missing_keys)}")
                statuses.append("critical" if empty else "warning")

            if age_hours is not None:
                if age_hours > STALE_HOURS:
                    issues.append(f"No new data for {age_hours:.0f}h")
                    statuses.append("critical")
                elif age_hours > FRESH_HOURS:
                    issues.append(f"Last data {age_hours:.0f}h ago")
                    statuses.append("warning")

        snapshots = int(getattr(counts, "snapshots", 0) or 0)
        days_covered = int(getattr(counts, "days_covered", 0) or 0)
        if days_covered < days:
            missed = days - days_covered
            issues.append(f"Missing data on {missed} of the last {days} days")
            # A single missed day happens; half the window missing doesn't.
            statuses.append("critical" if missed * 2 > days else "warning")

        posts_total = int(getattr(posts, "total", 0) or 0)
        null_likes = int(getattr(posts, "null_likes", 0) or 0)
        null_comments = int(getattr(posts, "null_comments", 0) or 0)
        if posts_total == 0:
            issues.append("No posts collected for this page")
            statuses.append("warning")
        if null_likes:
            issues.append(f"{null_likes}/{posts_total} posts missing likes")
            statuses.append("warning")
        if null_comments:
            issues.append(f"{null_comments}/{posts_total} posts missing comments")
            statuses.append("warning")

        return {
            "page_id": str(page.uuid),
            "page_name": page.name,
            "page_link": page.link,
            "platform": page.platform,
            "status": _worst(statuses),
            "issues": issues,
            "last_snapshot_at": iso_utc(getattr(latest, "recorded_at", None)),
            "last_snapshot_source": getattr(latest, "source", None),
            "age_hours": age_hours,
            "missing_keys": missing_keys,
            "snapshots_in_window": snapshots,
            "days_covered": days_covered,
            "days_expected": days,
            "posts_total": posts_total,
            "posts_null_likes": null_likes,
            "posts_null_comments": null_comments,
            "last_post_at": iso_utc(getattr(posts, "last_recorded_at", None)),
        }

    # ── Run a scrape for one client, then check it landed ─────────────────

    @staticmethod
    def trigger_scrape(entity_id: int, platform: str, mode: str,
                       requested_by: int | None = None) -> dict:
        """Queue an own-scraper run on behalf of one client. The run itself
        is platform-wide (see the module docstring); this validates that the
        client actually has a page on that platform, so an admin can't fire
        a LinkedIn run for a brand that has no LinkedIn page and then wait
        for data that was never going to arrive."""
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise PriorityEntityError(f"No entity with id {entity_id}.")

        pages = PriorityEntityRepository.get_pages_for_entities([entity_id])
        platforms = {p.platform for p in pages}
        if platform not in platforms:
            have = ", ".join(sorted(platforms)) or "none"
            raise PriorityEntityError(
                f"'{entity.name}' has no {platform} page (tracked platforms: {have})."
            )

        try:
            trigger = ScrapeTriggerService.request_trigger(
                platform=platform, mode=mode, requested_by=requested_by, entity_id=entity_id
            )
        except ScrapeTriggerError as exc:
            raise PriorityEntityError(str(exc)) from exc

        return trigger

    @staticmethod
    def verify_scrape(entity_id: int, trigger_id: int) -> dict:
        """Did the run actually produce data for *this* client?

        Compares each of the entity's pages on the run's platform against
        the moment the run was queued. A run that systemd reported as
        "done" can still have brought back nothing for a particular page
        (login expired mid-run, that page 404s, it was skipped as
        not-due) -- which is exactly the failure this whole page exists to
        catch, so status alone is never treated as proof.
        """
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise PriorityEntityError(f"No entity with id {entity_id}.")

        trigger = ScrapeTriggerService.get(trigger_id)
        if trigger is None:
            raise PriorityEntityError(f"No trigger request with id {trigger_id}.")
        if trigger.get("entity_id") not in (None, entity_id):
            raise PriorityEntityError(
                f"Trigger #{trigger_id} was fired for a different entity."
            )

        requested_at = trigger.get("requested_at")
        since = datetime.fromisoformat(requested_at) if requested_at else None
        if since is None:
            raise PriorityEntityError(f"Trigger #{trigger_id} has no requested_at to compare against.")
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        pages = [
            p
            for p in PriorityEntityRepository.get_pages_for_entities([entity_id])
            if p.platform == trigger["platform"]
        ]
        page_ids = [p.uuid for p in pages]

        snapshots = {
            str(row.page_id): int(row.snapshots or 0)
            for row in PriorityEntityRepository.count_history_since(page_ids, since)
        }
        posts = {
            str(row.page_id): int(row.posts or 0)
            for row in PriorityEntityRepository.count_posts_since(page_ids, since)
        }

        results = []
        for page in pages:
            key = str(page.uuid)
            new_snapshots = snapshots.get(key, 0)
            new_posts = posts.get(key, 0)
            results.append(
                {
                    "page_id": key,
                    "page_name": page.name,
                    "page_link": page.link,
                    "platform": page.platform,
                    "new_snapshots": new_snapshots,
                    "new_posts": new_posts,
                    "scraped": new_snapshots > 0 or new_posts > 0,
                }
            )

        scraped_pages = sum(1 for r in results if r["scraped"])
        return {
            "entity_id": entity_id,
            "entity_name": entity.name,
            "trigger": trigger,
            "since": iso_utc(since),
            "pages_checked": len(results),
            "pages_with_new_data": scraped_pages,
            # Only a finished run can be judged; while it's pending/running
            # an empty result just means "not yet", not "it failed".
            "verdict": PriorityEntityService._verdict(trigger["status"], len(results), scraped_pages),
            "pages": results,
        }

    @staticmethod
    def _verdict(trigger_status: str, pages_checked: int, pages_with_new_data: int) -> str:
        if pages_with_new_data and pages_with_new_data == pages_checked:
            return "scraped"
        if pages_with_new_data:
            return "partial"
        if trigger_status in ("pending", "running"):
            return "waiting"
        return "no_data"
