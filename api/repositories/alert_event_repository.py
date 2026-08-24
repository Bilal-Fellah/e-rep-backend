from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from api import db
from api.models.alert_event_model import AlertEvent
from api.models.user_alert_model import UserAlert
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class AlertEventRepository:
    @staticmethod
    def create_or_get(event_data: dict, commit: bool = True) -> tuple[AlertEvent, bool]:
        existing = AlertEvent.query.filter_by(dedupe_key=event_data["dedupe_key"]).first()
        if existing:
            return existing, False

        event = AlertEvent(**event_data)
        db.session.add(event)
        try:
            if commit:
                db.session.commit()
            else:
                db.session.flush()
            return event, True
        except IntegrityError:
            db.session.rollback()
            existing = AlertEvent.query.filter_by(dedupe_key=event_data["dedupe_key"]).first()
            if existing:
                return existing, False
            raise

    @staticmethod
    def get_historical_events_for_rule(
        event_type: str,
        entity_scope: dict | None,
        user_id: int,
        lookback_days: int,
        max_events: int,
    ) -> list[AlertEvent]:
        """
        Fetch historical events that match rule criteria and don't already have
        a user alert for this user.

        Args:
            event_type: Type of event to match
            entity_scope: Entity filter from rule
            user_id: User ID to check for existing alerts
            lookback_days: Only consider events from last N days
            max_events: Maximum number of events to return

        Returns:
            List of AlertEvent objects
        """
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)

        q = AlertEvent.query.filter(
            AlertEvent.event_type == event_type,
            AlertEvent.event_at >= cutoff_date,
        )

        # Apply entity scope filter
        if entity_scope and isinstance(entity_scope, dict):
            entity_ids = entity_scope.get("entity_ids")
            if entity_ids:
                q = q.filter(AlertEvent.entity_id.in_(entity_ids))

        # Exclude events that already have user alerts for this user
        q = (
            q.outerjoin(
                UserAlert,
                db.and_(
                    UserAlert.event_id == AlertEvent.id,
                    UserAlert.user_id == user_id,
                ),
            )
            .filter(UserAlert.id.is_(None))
        )

        # Order by most recent first and apply limit
        return q.order_by(AlertEvent.event_at.desc()).limit(max_events).all()

    @staticmethod
    def fanout_to_users(event_id: int, rule_ids_by_user: dict[int, int], commit: bool = True) -> int:
        inserted = 0
        for user_id, rule_id in rule_ids_by_user.items():
            existing = UserAlert.query.filter_by(
                user_id=user_id, event_id=event_id, rule_id=rule_id
            ).first()
            if existing:
                continue
            row = UserAlert()
            row.user_id = user_id
            row.event_id = event_id
            row.rule_id = rule_id
            row.status = "unread"
            db.session.add(row)
            inserted += 1

        if commit:
            db.session.commit()
        return inserted

    @staticmethod
    def list_user_alerts(
        user_id: int,
        *,
        status: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        q = (
            db.session.query(UserAlert, AlertEvent)
            .join(AlertEvent, AlertEvent.id == UserAlert.event_id)
            .filter(UserAlert.user_id == user_id)
        )
        if status:
            q = q.filter(UserAlert.status == status)
        if event_type:
            q = q.filter(AlertEvent.event_type == event_type)

        return (
            q.order_by(UserAlert.created_at.desc(), UserAlert.id.desc())
            .limit(max(1, min(int(limit), 200)))
            .offset(max(0, int(offset)))
            .all()
        )

    @staticmethod
    def count_user_unread(user_id: int) -> int:
        return UserAlert.query.filter_by(user_id=user_id, status="unread").count()

    @staticmethod
    def mark_read(user_alert: UserAlert, commit: bool = True) -> UserAlert:
        if user_alert.status != "read":
            user_alert.status = "read"
            user_alert.read_at = datetime.utcnow()
        if commit:
            db.session.commit()
        return user_alert

    @staticmethod
    def mark_dismissed(user_alert: UserAlert, commit: bool = True) -> UserAlert:
        if user_alert.status != "dismissed":
            user_alert.status = "dismissed"
            user_alert.dismissed_at = datetime.utcnow()
        if commit:
            db.session.commit()
        return user_alert

    @staticmethod
    def mark_all_read(user_id: int, commit: bool = True) -> int:
        now = datetime.utcnow()
        count = (
            UserAlert.query
            .filter(UserAlert.user_id == user_id, UserAlert.status == "unread")
            .update({UserAlert.status: "read", UserAlert.read_at: now}, synchronize_session=False)
        )
        if commit:
            db.session.commit()
        return count

    @staticmethod
    def get_user_alert(user_alert_id: int, user_id: int) -> UserAlert | None:
        return UserAlert.query.filter_by(id=user_alert_id, user_id=user_id).first()
