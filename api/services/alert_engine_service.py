from datetime import datetime, timedelta

from sqlalchemy import String, cast, func

from api import db
from api.models.comment_model import Comment
from api.models.page_model import Page
from api.models.post_model import PostMV, PostHistoryMV
from api.models.scraping_post_result_model import ScrapingPostResult
from api.models.scraping_session_model import ScrapingSession
from api.repositories.alert_detector_checkpoint_repository import (
    AlertDetectorCheckpointRepository,
)
from api.repositories.alert_event_repository import AlertEventRepository
from api.repositories.alert_rule_repository import AlertRuleRepository

from api.services.alert_service import AlertService, normalize_keyword
from api.utils.logging_utils import instrument_service_class


DETECTOR_NEGATIVE = "negative_comment"
DETECTOR_KEYWORD_COMMENT = "keyword_comment"
DETECTOR_KEYWORD_POST = "keyword_post"
DETECTOR_ENGAGEMENT = "engagement_anomaly"
MARKER_MV_REFRESH = "mv_refresh"

DEFAULT_READINESS_MAX_UNPROCESSED = 0
DEFAULT_READINESS_FRESHNESS_MINUTES = 180
DEFAULT_ENGAGEMENT_LOOKBACK_DAYS = 8
DEFAULT_ENGAGEMENT_MIN_BASELINE = 20
DEFAULT_ENGAGEMENT_PCT_UP = 0.50
DEFAULT_ENGAGEMENT_PCT_DOWN = 0.50
DEFAULT_ENGAGEMENT_MIN_ABS_CHANGE = 10


@instrument_service_class
class AlertEngineService:
    @staticmethod
    def _env_int(name: str, default: int) -> int:
        import os

        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        import os

        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def get_readiness() -> dict:
        now = datetime.utcnow()
        freshness_minutes = AlertEngineService._env_int(
            "ALERTS_READINESS_FRESHNESS_MINUTES", DEFAULT_READINESS_FRESHNESS_MINUTES
        )
        max_unprocessed = AlertEngineService._env_int(
            "ALERTS_READINESS_MAX_UNPROCESSED", DEFAULT_READINESS_MAX_UNPROCESSED
        )

        latest = ScrapingSession.query.order_by(ScrapingSession.created_at.desc()).first()
        if not latest:
            return {
                "ready": False,
                "reason": "No scraping sessions found",
                "context": {},
            }

        if latest.status != "completed" or not latest.completed_at:
            return {
                "ready": False,
                "reason": "Latest scraping session is not completed",
                "context": {
                    "latest_session_id": latest.session_id,
                    "latest_session_status": latest.status,
                },
            }

        freshness_deadline = now - timedelta(minutes=freshness_minutes)
        if latest.completed_at < freshness_deadline:
            return {
                "ready": False,
                "reason": "Latest completed scraping session is too old",
                "context": {
                    "latest_session_id": latest.session_id,
                    "latest_completed_at": latest.completed_at.isoformat(),
                    "freshness_deadline": freshness_deadline.isoformat(),
                },
            }

        comment_count = (
            Comment.query.filter(Comment.scraping_session_id == latest.session_id).count()
        )
        result_count = (
            ScrapingPostResult.query.filter(
                ScrapingPostResult.scraping_session_id == latest.session_id
            ).count()
        )
        if comment_count == 0 and result_count == 0:
            return {
                "ready": False,
                "reason": "No comments or post-results found for latest completed scraping session",
                "context": {
                    "latest_session_id": latest.session_id,
                    "comments_in_session": comment_count,
                    "post_results_in_session": result_count,
                },
            }

        # Readiness should be based on the latest ingestion cycle, not global
        # historical backlog. We use unlabeled count in the latest completed
        # scraping session as the "labeling finished" signal.
        unlabeled_in_latest_session = (
            Comment.query.filter(
                Comment.scraping_session_id == latest.session_id,
                Comment.label.is_(None),
            ).count()
        )
        if unlabeled_in_latest_session > max_unprocessed:
            return {
                "ready": False,
                "reason": "Latest session still has unlabeled comments above threshold",
                "context": {
                    "latest_session_id": latest.session_id,
                    "unlabeled_comments_in_latest_session": unlabeled_in_latest_session,
                    "max_allowed_unlabeled": max_unprocessed,
                },
            }

        mv_marker = AlertDetectorCheckpointRepository.get(MARKER_MV_REFRESH)
        if not mv_marker or not mv_marker.cursor_ts:
            return {
                "ready": False,
                "reason": "Materialized-view refresh marker missing",
                "context": {
                    "latest_session_id": latest.session_id,
                    "latest_completed_at": latest.completed_at.isoformat(),
                },
            }

        if mv_marker.cursor_ts < latest.completed_at:
            return {
                "ready": False,
                "reason": "Materialized views were not refreshed after latest completed scraping session",
                "context": {
                    "latest_session_id": latest.session_id,
                    "latest_completed_at": latest.completed_at.isoformat(),
                    "last_mv_refresh_at": mv_marker.cursor_ts.isoformat(),
                },
            }

        return {
            "ready": True,
            "reason": None,
            "context": {
                "latest_completed_scraping_session": latest.session_id,
                "latest_completed_at": latest.completed_at.isoformat(),
                "comments_in_session": comment_count,
                "post_results_in_session": result_count,
                "unlabeled_comments_in_latest_session": unlabeled_in_latest_session,
                "last_mv_refresh_at": mv_marker.cursor_ts.isoformat(),
            },
        }

    @staticmethod
    def mark_mv_refreshed(at: datetime | None = None) -> None:
        AlertDetectorCheckpointRepository.upsert(
            MARKER_MV_REFRESH,
            cursor_ts=at or datetime.utcnow(),
            commit=True,
        )

    @staticmethod
    def run(detectors: list[str] | None = None, dry_run: bool = False) -> dict:
        detector_order = [
            DETECTOR_NEGATIVE,
            DETECTOR_KEYWORD_COMMENT,
            DETECTOR_KEYWORD_POST,
            DETECTOR_ENGAGEMENT,
        ]
        selected = set(detectors or detector_order)

        summary = {
            "run_at": datetime.utcnow().isoformat(),
            "dry_run": bool(dry_run),
            "detectors": {},
            "events_created": 0,
            "user_alerts_created": 0,
        }

        if DETECTOR_NEGATIVE in selected:
            s = AlertEngineService._run_negative_comment_detector(dry_run=dry_run)
            summary["detectors"][DETECTOR_NEGATIVE] = s
            summary["events_created"] += s["events_created"]
            summary["user_alerts_created"] += s["user_alerts_created"]

        if DETECTOR_KEYWORD_COMMENT in selected:
            s = AlertEngineService._run_keyword_comment_detector(dry_run=dry_run)
            summary["detectors"][DETECTOR_KEYWORD_COMMENT] = s
            summary["events_created"] += s["events_created"]
            summary["user_alerts_created"] += s["user_alerts_created"]

        if DETECTOR_KEYWORD_POST in selected:
            s = AlertEngineService._run_keyword_post_detector(dry_run=dry_run)
            summary["detectors"][DETECTOR_KEYWORD_POST] = s
            summary["events_created"] += s["events_created"]
            summary["user_alerts_created"] += s["user_alerts_created"]

        if DETECTOR_ENGAGEMENT in selected:
            s = AlertEngineService._run_engagement_anomaly_detector(dry_run=dry_run)
            summary["detectors"][DETECTOR_ENGAGEMENT] = s
            summary["events_created"] += s["events_created"]
            summary["user_alerts_created"] += s["user_alerts_created"]

        return summary

    @staticmethod
    def _page_entity_map(page_ids: list[str]) -> dict[str, int]:
        if not page_ids:
            return {}
        rows = (
            db.session.query(cast(Page.uuid, String), Page.entity_id)
            .filter(cast(Page.uuid, String).in_(page_ids))
            .all()
        )
        return {str(pid): entity_id for pid, entity_id in rows}

    @staticmethod
    def _fanout_event_to_matching_rules(event, event_type: str, entity_id: int | None, dry_run: bool = False) -> int:
        rules = AlertRuleRepository.list_matching_rules(event_type, entity_id)
        if not rules:
            return 0

        mapping = {}
        for rule in rules:
            mapping[rule.user_id] = rule.id

        if dry_run:
            return len(mapping)

        return AlertEventRepository.fanout_to_users(event.id, mapping, commit=True)

    @staticmethod
    def _run_negative_comment_detector(dry_run: bool = False) -> dict:
        cursor = AlertDetectorCheckpointRepository.get_cursor_ts(DETECTOR_NEGATIVE)
        event_ts_expr = func.coalesce(Comment.label_updated_at, Comment.recorded_at)
        q = Comment.query.filter(Comment.label.in_([0, 1]))
        if cursor:
            q = q.filter(event_ts_expr > cursor)
        rows = q.order_by(event_ts_expr.asc()).all()

        if not rows:
            return {
                "scanned": 0,
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": cursor.isoformat() if cursor else None,
            }

        page_map = AlertEngineService._page_entity_map(list({str(r.page_id) for r in rows}))

        events_created = 0
        user_alerts_created = 0
        max_ts = cursor

        for row in rows:
            entity_id = page_map.get(str(row.page_id))
            dedupe_key = f"neg_comment:{row.id}:{row.label}"
            event_data = {
                "event_type": "negative_comment",
                "dedupe_key": dedupe_key,
                "severity": "serious" if row.label == 0 else "warning",
                "entity_id": entity_id,
                "page_id": str(row.page_id),
                "platform": row.platform,
                "post_id": row.post_id,
                "comment_pk": row.id,
                "label": row.label,
                "matched_keyword": None,
                "payload": {
                    "text": row.text,
                    "author_username": row.author_username,
                    "confidence": row.confidence,
                },
                "event_at": row.label_updated_at or row.recorded_at,
            }

            if dry_run:
                events_created += 1
                user_alerts_created += len(
                    AlertRuleRepository.list_matching_rules("negative_comment", entity_id)
                )
            else:
                event, created = AlertEventRepository.create_or_get(event_data, commit=True)
                if created:
                    events_created += 1
                user_alerts_created += AlertEngineService._fanout_event_to_matching_rules(
                    event,
                    "negative_comment",
                    entity_id,
                    dry_run=False,
                )

            row_event_ts = row.label_updated_at or row.recorded_at
            if row_event_ts and (max_ts is None or row_event_ts > max_ts):
                max_ts = row_event_ts

        if max_ts and not dry_run:
            AlertDetectorCheckpointRepository.upsert(DETECTOR_NEGATIVE, cursor_ts=max_ts)

        return {
            "scanned": len(rows),
            "events_created": events_created,
            "user_alerts_created": user_alerts_created,
            "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
        }

    @staticmethod
    def _keyword_rules_by_entity_and_mode() -> list[tuple]:
        rules = AlertRuleRepository.list_active_by_event_type("keyword_mention")
        if not rules:
            return []
        kw_map = AlertRuleRepository.list_keywords_for_rule_ids([r.id for r in rules])

        rows: list[tuple] = []
        for rule in rules:
            kws = kw_map.get(rule.id, [])
            if not kws:
                continue
            rows.append((rule, kws))
        return rows

    @staticmethod
    def _rule_matches_entity(rule, entity_id: int | None) -> bool:
        scope = rule.entity_scope or {}
        ids = scope.get("entity_ids") if isinstance(scope, dict) else None
        if not ids:
            return True
        if entity_id is None:
            return False
        return entity_id in ids

    @staticmethod
    def _run_keyword_comment_detector(dry_run: bool = False) -> dict:
        cursor = AlertDetectorCheckpointRepository.get_cursor_ts(DETECTOR_KEYWORD_COMMENT)
        q = Comment.query
        if cursor:
            q = q.filter(Comment.recorded_at > cursor)
        rows = q.order_by(Comment.recorded_at.asc()).all()

        if not rows:
            return {
                "scanned": 0,
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": cursor.isoformat() if cursor else None,
            }

        rule_rows = AlertEngineService._keyword_rules_by_entity_and_mode()
        if not rule_rows:
            max_ts = rows[-1].recorded_at
            if max_ts and not dry_run:
                AlertDetectorCheckpointRepository.upsert(
                    DETECTOR_KEYWORD_COMMENT, cursor_ts=max_ts
                )
            return {
                "scanned": len(rows),
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
            }

        page_map = AlertEngineService._page_entity_map(list({str(r.page_id) for r in rows}))

        events_created = 0
        user_alerts_created = 0

        for row in rows:
            entity_id = page_map.get(str(row.page_id))
            source_text = row.text or ""
            source_norm = normalize_keyword(source_text)

            for rule, keywords in rule_rows:
                if not AlertEngineService._rule_matches_entity(rule, entity_id):
                    continue

                for kw in keywords:
                    if not AlertService.match_keyword(
                        text_original=source_text,
                        text_normalized=source_norm,
                        keyword_original=kw.keyword,
                        keyword_normalized=kw.keyword_normalized,
                        match_mode=rule.match_mode,
                        is_case_sensitive=bool(rule.is_case_sensitive),
                    ):
                        continue

                    dedupe_key = f"kw:c:{row.id}:{kw.keyword_normalized}"
                    event_data = {
                        "event_type": "keyword_mention",
                        "dedupe_key": dedupe_key,
                        "severity": "warning",
                        "entity_id": entity_id,
                        "page_id": str(row.page_id),
                        "platform": row.platform,
                        "post_id": row.post_id,
                        "comment_pk": row.id,
                        "matched_keyword": kw.keyword,
                        "payload": {
                            "source": "comment",
                            "text": row.text,
                            "keyword_normalized": kw.keyword_normalized,
                            "rule_id": rule.id,
                        },
                        "event_at": row.recorded_at,
                    }

                    if dry_run:
                        events_created += 1
                        user_alerts_created += 1
                    else:
                        event, created = AlertEventRepository.create_or_get(event_data)
                        if created:
                            events_created += 1
                        user_alerts_created += AlertEventRepository.fanout_to_users(
                            event.id,
                            {rule.user_id: rule.id},
                            commit=True,
                        )

        max_ts = rows[-1].recorded_at
        if max_ts and not dry_run:
            AlertDetectorCheckpointRepository.upsert(
                DETECTOR_KEYWORD_COMMENT, cursor_ts=max_ts
            )

        return {
            "scanned": len(rows),
            "events_created": events_created,
            "user_alerts_created": user_alerts_created,
            "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
        }

    @staticmethod
    def _run_keyword_post_detector(dry_run: bool = False) -> dict:
        cursor = AlertDetectorCheckpointRepository.get_cursor_ts(DETECTOR_KEYWORD_POST)
        q = PostMV.query
        if cursor:
            q = q.filter(PostMV.recorded_at > cursor)
        rows = q.order_by(PostMV.recorded_at.asc()).all()

        if not rows:
            return {
                "scanned": 0,
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": cursor.isoformat() if cursor else None,
            }

        rule_rows = AlertEngineService._keyword_rules_by_entity_and_mode()
        if not rule_rows:
            max_ts = rows[-1].recorded_at
            if max_ts and not dry_run:
                AlertDetectorCheckpointRepository.upsert(
                    DETECTOR_KEYWORD_POST, cursor_ts=max_ts
                )
            return {
                "scanned": len(rows),
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
            }

        page_map = AlertEngineService._page_entity_map(list({str(r.page_id) for r in rows}))

        events_created = 0
        user_alerts_created = 0

        for row in rows:
            source_text = row.caption or ""
            if not source_text:
                continue
            source_norm = normalize_keyword(source_text)
            entity_id = page_map.get(str(row.page_id))

            for rule, keywords in rule_rows:
                if not AlertEngineService._rule_matches_entity(rule, entity_id):
                    continue

                for kw in keywords:
                    if not AlertService.match_keyword(
                        text_original=source_text,
                        text_normalized=source_norm,
                        keyword_original=kw.keyword,
                        keyword_normalized=kw.keyword_normalized,
                        match_mode=rule.match_mode,
                        is_case_sensitive=bool(rule.is_case_sensitive),
                    ):
                        continue

                    dedupe_key = (
                        f"kw:p:{row.page_id}:{row.platform}:{row.post_id}:{kw.keyword_normalized}"
                    )
                    event_data = {
                        "event_type": "keyword_mention",
                        "dedupe_key": dedupe_key,
                        "severity": "warning",
                        "entity_id": entity_id,
                        "page_id": str(row.page_id),
                        "platform": row.platform,
                        "post_id": row.post_id,
                        "matched_keyword": kw.keyword,
                        "payload": {
                            "source": "post",
                            "text": row.caption,
                            "keyword_normalized": kw.keyword_normalized,
                            "rule_id": rule.id,
                        },
                        "event_at": row.recorded_at or row.created_at or datetime.utcnow(),
                    }

                    if dry_run:
                        events_created += 1
                        user_alerts_created += 1
                    else:
                        event, created = AlertEventRepository.create_or_get(event_data)
                        if created:
                            events_created += 1
                        user_alerts_created += AlertEventRepository.fanout_to_users(
                            event.id,
                            {rule.user_id: rule.id},
                            commit=True,
                        )

        max_ts = rows[-1].recorded_at
        if max_ts and not dry_run:
            AlertDetectorCheckpointRepository.upsert(
                DETECTOR_KEYWORD_POST, cursor_ts=max_ts
            )

        return {
            "scanned": len(rows),
            "events_created": events_created,
            "user_alerts_created": user_alerts_created,
            "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
        }

    @staticmethod
    def _metric_value(row, name: str):
        return getattr(row, name, None)

    @staticmethod
    def _is_suspicious_zero(current_value, previous_valid_value) -> bool:
        if current_value is None:
            return False
        if previous_valid_value is None:
            return False
        try:
            return float(previous_valid_value) > 0 and float(current_value) == 0.0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _run_engagement_anomaly_detector(dry_run: bool = False) -> dict:
        cursor = AlertDetectorCheckpointRepository.get_cursor_ts(DETECTOR_ENGAGEMENT)
        lookback_days = AlertEngineService._env_int(
            "ALERTS_ENGAGEMENT_LOOKBACK_DAYS", DEFAULT_ENGAGEMENT_LOOKBACK_DAYS
        )
        threshold_up = AlertEngineService._env_float(
            "ALERTS_ENGAGEMENT_THRESHOLD_UP", DEFAULT_ENGAGEMENT_PCT_UP
        )
        threshold_down = AlertEngineService._env_float(
            "ALERTS_ENGAGEMENT_THRESHOLD_DOWN", DEFAULT_ENGAGEMENT_PCT_DOWN
        )
        min_baseline = AlertEngineService._env_int(
            "ALERTS_ENGAGEMENT_MIN_BASELINE", DEFAULT_ENGAGEMENT_MIN_BASELINE
        )
        min_abs_change = AlertEngineService._env_int(
            "ALERTS_ENGAGEMENT_MIN_ABS_CHANGE", DEFAULT_ENGAGEMENT_MIN_ABS_CHANGE
        )

        start_from = cursor - timedelta(days=lookback_days) if cursor else datetime.utcnow() - timedelta(days=lookback_days)
        rows = (
            PostHistoryMV.query
            .filter(PostHistoryMV.recorded_at >= start_from)
            .order_by(
                PostHistoryMV.page_id.asc(),
                PostHistoryMV.platform.asc(),
                PostHistoryMV.post_id.asc(),
                PostHistoryMV.recorded_at.asc(),
            )
            .all()
        )

        if not rows:
            return {
                "scanned": 0,
                "events_created": 0,
                "user_alerts_created": 0,
                "cursor_advanced_to": cursor.isoformat() if cursor else None,
            }

        grouped: dict[tuple, list] = {}
        for row in rows:
            key = (str(row.page_id), row.platform, row.post_id)
            grouped.setdefault(key, []).append(row)

        page_ids = [k[0] for k in grouped.keys()]
        page_map = AlertEngineService._page_entity_map(page_ids)

        metrics = ["likes", "comments", "shares", "views"]
        events_created = 0
        user_alerts_created = 0
        max_ts = cursor

        for (page_id, platform, post_id), snaps in grouped.items():
            if len(snaps) < 3:
                continue
            latest = snaps[-1]
            prev = snaps[-2]
            entity_id = page_map.get(page_id)

            for metric in metrics:
                current = AlertEngineService._metric_value(latest, metric)
                prev_value = AlertEngineService._metric_value(prev, metric)

                if current is None or prev_value is None:
                    continue

                # Mandatory anti-noise rule: 0 after positive is considered scraper/data error.
                if AlertEngineService._is_suspicious_zero(current, prev_value):
                    continue

                # Build baseline from previous valid points only and exclude suspicious zeros.
                baseline_values: list[float] = []
                previous_valid = None
                for s in snaps[:-1]:
                    v = AlertEngineService._metric_value(s, metric)
                    if v is None:
                        continue
                    if AlertEngineService._is_suspicious_zero(v, previous_valid):
                        continue
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    baseline_values.append(fv)
                    previous_valid = fv

                if len(baseline_values) < 3:
                    continue

                baseline_values_sorted = sorted(baseline_values)
                baseline = baseline_values_sorted[len(baseline_values_sorted) // 2]
                if baseline < min_baseline:
                    continue

                try:
                    curr = float(current)
                except (TypeError, ValueError):
                    continue

                abs_change = curr - baseline
                if abs(abs_change) < min_abs_change:
                    continue

                deviation = abs_change / baseline if baseline else 0.0

                direction = None
                severity = None
                if deviation >= threshold_up:
                    direction = "increase"
                    severity = "warning"
                elif deviation <= -threshold_down:
                    direction = "drop"
                    severity = "serious"

                if not direction:
                    continue

                bucket_time = latest.recorded_at.replace(minute=0, second=0, microsecond=0)
                dedupe_key = (
                    f"eng:{page_id}:{platform}:{post_id}:{metric}:{direction}:{bucket_time.isoformat()}"
                )

                event_data = {
                    "event_type": "engagement_anomaly",
                    "dedupe_key": dedupe_key,
                    "severity": severity,
                    "entity_id": entity_id,
                    "page_id": page_id,
                    "platform": platform,
                    "post_id": post_id,
                    "payload": {
                        "metric": metric,
                        "direction": direction,
                        "baseline": baseline,
                        "current": curr,
                        "deviation": round(deviation, 4),
                        "abs_change": round(abs_change, 4),
                        "latest_recorded_at": latest.recorded_at.isoformat(),
                    },
                    "event_at": latest.recorded_at,
                }

                if dry_run:
                    events_created += 1
                    user_alerts_created += len(
                        AlertRuleRepository.list_matching_rules(
                            "engagement_anomaly", entity_id
                        )
                    )
                else:
                    event, created = AlertEventRepository.create_or_get(event_data)
                    if created:
                        events_created += 1
                    user_alerts_created += AlertEngineService._fanout_event_to_matching_rules(
                        event,
                        "engagement_anomaly",
                        entity_id,
                        dry_run=False,
                    )

            if latest.recorded_at and (max_ts is None or latest.recorded_at > max_ts):
                max_ts = latest.recorded_at

        if max_ts and not dry_run:
            AlertDetectorCheckpointRepository.upsert(DETECTOR_ENGAGEMENT, cursor_ts=max_ts)

        return {
            "scanned": len(rows),
            "events_created": events_created,
            "user_alerts_created": user_alerts_created,
            "cursor_advanced_to": max_ts.isoformat() if max_ts else None,
        }
