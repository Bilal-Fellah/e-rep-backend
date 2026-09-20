# Data-access methods for client entity link repository.
from api.models.client_entity_link_model import ClientEntityLink, db
from api.models.entity_model import Entity
from api.models.user_model import User
from api.utils.logging_utils import instrument_repository_class


@instrument_repository_class
class ClientEntityLinkRepository:
    """Repository for client_entity_links database operations."""

    @staticmethod
    def get_by_id(link_id: int) -> ClientEntityLink | None:
        return db.session.get(ClientEntityLink, link_id)

    @staticmethod
    def get_for_pair(user_id: int, entity_id: int) -> ClientEntityLink | None:
        return ClientEntityLink.query.filter_by(user_id=user_id, entity_id=entity_id).first()

    @staticmethod
    def list_for_user(user_id: int) -> list:
        """One client's links, joined to the company so the caller doesn't
        need a second query for the name."""
        return (
            db.session.query(
                ClientEntityLink.id,
                ClientEntityLink.user_id,
                ClientEntityLink.entity_id,
                ClientEntityLink.status,
                ClientEntityLink.role,
                ClientEntityLink.note,
                ClientEntityLink.review_note,
                ClientEntityLink.requested_at,
                ClientEntityLink.reviewed_at,
                Entity.name.label("entity_name"),
                Entity.type.label("entity_type"),
            )
            .join(Entity, Entity.id == ClientEntityLink.entity_id)
            .filter(ClientEntityLink.user_id == user_id)
            .order_by(ClientEntityLink.requested_at.desc())
            .all()
        )

    @staticmethod
    def list_all(status: str | None = None, limit: int = 200) -> list:
        """Admin view: every link with both sides resolved. Pending first --
        those are the ones waiting on a decision."""
        query = (
            db.session.query(
                ClientEntityLink.id,
                ClientEntityLink.user_id,
                ClientEntityLink.entity_id,
                ClientEntityLink.status,
                ClientEntityLink.role,
                ClientEntityLink.note,
                ClientEntityLink.review_note,
                ClientEntityLink.requested_at,
                ClientEntityLink.reviewed_at,
                ClientEntityLink.reviewed_by,
                Entity.name.label("entity_name"),
                Entity.type.label("entity_type"),
                User.email.label("user_email"),
                User.first_name.label("user_first_name"),
                User.last_name.label("user_last_name"),
                User.role.label("user_role"),
            )
            .join(Entity, Entity.id == ClientEntityLink.entity_id)
            .join(User, User.id == ClientEntityLink.user_id)
        )
        if status:
            query = query.filter(ClientEntityLink.status == status)
        return (
            query.order_by(
                # Pending first regardless of age, then newest activity.
                (ClientEntityLink.status != "pending"),
                ClientEntityLink.requested_at.desc(),
            )
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_by_status() -> dict:
        rows = (
            db.session.query(ClientEntityLink.status, db.func.count())
            .group_by(ClientEntityLink.status)
            .all()
        )
        return {status: int(count) for status, count in rows}

    @staticmethod
    def create(user_id: int, entity_id: int, status: str, role: str,
               note: str | None = None, commit: bool = True) -> ClientEntityLink:
        row = ClientEntityLink(
            user_id=user_id, entity_id=entity_id, status=status, role=role, note=note
        )
        db.session.add(row)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def save(row: ClientEntityLink, commit: bool = True) -> ClientEntityLink:
        db.session.add(row)
        if commit:
            db.session.commit()
        return row

    @staticmethod
    def delete(row: ClientEntityLink, commit: bool = True) -> None:
        db.session.delete(row)
        if commit:
            db.session.commit()

    @staticmethod
    def approved_users_for_entity(entity_id: int) -> list:
        """Who is approved on this company -- what the Priority page and any
        future 'who owns this brand' view needs."""
        return (
            db.session.query(
                ClientEntityLink.user_id,
                ClientEntityLink.role,
                User.email.label("user_email"),
                User.first_name.label("user_first_name"),
                User.last_name.label("user_last_name"),
            )
            .join(User, User.id == ClientEntityLink.user_id)
            .filter(
                ClientEntityLink.entity_id == entity_id,
                ClientEntityLink.status == "approved",
            )
            .order_by(ClientEntityLink.role, User.email)
            .all()
        )
