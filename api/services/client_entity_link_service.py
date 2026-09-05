# Service layer for linking client accounts to the companies they belong to.
#
# The flow is deliberately a claim followed by a human decision: a client
# asks to be added to a company from the app, and an admin approves or
# rejects it in Brendex Admin. Nothing links automatically -- anyone can
# claim to run any brand, so the approval is the part that makes it true.
#
# See api/models/client_entity_link_model.py for why this is many-to-many.
from datetime import datetime, timezone

from api.repositories.client_entity_link_repository import ClientEntityLinkRepository
from api.repositories.entity_repository import EntityRepository
from api.repositories.user_repository import UserRepository
from api.utils.datetime_utils import iso_utc
from api.utils.logging_utils import instrument_service_class

STATUSES = ("pending", "approved", "rejected")
ROLES = ("owner", "member")
DEFAULT_ROLE = "member"

MAX_NOTE_LENGTH = 500


class ClientEntityLinkError(ValueError):
    """Raised for an unknown user/company, a bad status or role, or a
    request that doesn't make sense (asking again for something already
    approved)."""


def _clean_note(note, field="note"):
    if note is None:
        return None
    note = str(note).strip()
    if not note:
        return None
    if len(note) > MAX_NOTE_LENGTH:
        raise ClientEntityLinkError(f"{field} must be at most {MAX_NOTE_LENGTH} characters.")
    return note


@instrument_service_class
class ClientEntityLinkService:
    # ── Client-facing ─────────────────────────────────────────────────────

    @staticmethod
    def request_link(user_id: int, entity_id: int, note=None) -> dict:
        """A client asks to be added to a company.

        Re-uses the existing row for a user/company pair rather than
        stacking duplicates: asking again after a rejection reopens the same
        request (and clears the old review), which is what someone who was
        told "not enough detail" will naturally do.
        """
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise ClientEntityLinkError(f"No company with id {entity_id}.")

        note = _clean_note(note)
        existing = ClientEntityLinkRepository.get_for_pair(user_id, entity_id)

        if existing is not None:
            if existing.status == "approved":
                raise ClientEntityLinkError(
                    f"You're already linked to '{entity.name}'."
                )
            if existing.status == "pending":
                # Let them update the note on a request still being reviewed
                # rather than telling them off for asking twice.
                if note is not None:
                    existing.note = note
                    ClientEntityLinkRepository.save(existing)
                return ClientEntityLinkService._serialize(existing, entity=entity)

            existing.status = "pending"
            existing.note = note
            existing.review_note = None
            existing.reviewed_at = None
            existing.reviewed_by = None
            ClientEntityLinkRepository.save(existing)
            return ClientEntityLinkService._serialize(existing, entity=entity)

        row = ClientEntityLinkRepository.create(
            user_id=user_id, entity_id=entity_id, status="pending",
            role=DEFAULT_ROLE, note=note,
        )
        return ClientEntityLinkService._serialize(row, entity=entity)

    @staticmethod
    def list_for_user(user_id: int) -> list[dict]:
        return [
            {
                "id": r.id,
                "entity_id": r.entity_id,
                "entity_name": r.entity_name,
                "entity_type": r.entity_type,
                "status": r.status,
                "role": r.role,
                "note": r.note,
                "review_note": r.review_note,
                "requested_at": iso_utc(r.requested_at),
                "reviewed_at": iso_utc(r.reviewed_at),
            }
            for r in ClientEntityLinkRepository.list_for_user(user_id)
        ]

    @staticmethod
    def withdraw(user_id: int, link_id: int) -> dict:
        """A client takes back a request they haven't had answered yet.
        Deliberately refuses to touch an approved link -- leaving a company
        is a decision for an admin, not a self-service delete."""
        row = ClientEntityLinkRepository.get_by_id(link_id)
        if row is None or row.user_id != user_id:
            raise ClientEntityLinkError(f"No request with id {link_id}.")
        if row.status == "approved":
            raise ClientEntityLinkError(
                "This link is already approved -- ask an admin to remove it."
            )
        ClientEntityLinkRepository.delete(row)
        return {"withdrawn_id": link_id}

    # ── Admin-facing ──────────────────────────────────────────────────────

    @staticmethod
    def list_all(status: str | None = None, limit: int = 200) -> dict:
        if status and status not in STATUSES:
            raise ClientEntityLinkError(f"status must be one of {STATUSES}.")
        rows = ClientEntityLinkRepository.list_all(status=status, limit=limit)
        return {
            "counts": ClientEntityLinkRepository.count_by_status(),
            "links": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "user_email": r.user_email,
                    "user_name": " ".join(
                        p for p in (r.user_first_name, r.user_last_name) if p
                    ) or None,
                    "user_role": r.user_role,
                    "entity_id": r.entity_id,
                    "entity_name": r.entity_name,
                    "entity_type": r.entity_type,
                    "status": r.status,
                    "role": r.role,
                    "note": r.note,
                    "review_note": r.review_note,
                    "requested_at": iso_utc(r.requested_at),
                    "reviewed_at": iso_utc(r.reviewed_at),
                    "reviewed_by": r.reviewed_by,
                }
                for r in rows
            ],
        }

    @staticmethod
    def approve(link_id: int, reviewed_by: int | None = None,
                role: str | None = None, review_note=None) -> dict:
        row = ClientEntityLinkRepository.get_by_id(link_id)
        if row is None:
            raise ClientEntityLinkError(f"No link request with id {link_id}.")
        if role is not None and role not in ROLES:
            raise ClientEntityLinkError(f"role must be one of {ROLES}.")

        row.status = "approved"
        if role is not None:
            row.role = role
        row.review_note = _clean_note(review_note, "review_note")
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by = reviewed_by
        ClientEntityLinkRepository.save(row)
        return ClientEntityLinkService._serialize(row)

    @staticmethod
    def reject(link_id: int, reviewed_by: int | None = None, review_note=None) -> dict:
        row = ClientEntityLinkRepository.get_by_id(link_id)
        if row is None:
            raise ClientEntityLinkError(f"No link request with id {link_id}.")

        row.status = "rejected"
        row.review_note = _clean_note(review_note, "review_note")
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by = reviewed_by
        ClientEntityLinkRepository.save(row)
        return ClientEntityLinkService._serialize(row)

    @staticmethod
    def link_directly(user_id: int, entity_id: int, reviewed_by: int | None = None,
                      role: str = DEFAULT_ROLE, review_note=None) -> dict:
        """Admin links a client to a company without waiting for them to ask
        -- the common case when the arrangement was agreed off-platform."""
        if role not in ROLES:
            raise ClientEntityLinkError(f"role must be one of {ROLES}.")
        if UserRepository.get_by_id(user_id) is None:
            raise ClientEntityLinkError(f"No user with id {user_id}.")
        entity = EntityRepository.get_by_id(entity_id)
        if entity is None:
            raise ClientEntityLinkError(f"No company with id {entity_id}.")

        row = ClientEntityLinkRepository.get_for_pair(user_id, entity_id)
        if row is not None and row.status == "approved":
            raise ClientEntityLinkError(
                f"That client is already linked to '{entity.name}'."
            )

        note = _clean_note(review_note, "review_note")
        if row is None:
            row = ClientEntityLinkRepository.create(
                user_id=user_id, entity_id=entity_id, status="approved",
                role=role, note=None, commit=False,
            )
        else:
            row.status = "approved"
            row.role = role
        row.review_note = note
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by = reviewed_by
        ClientEntityLinkRepository.save(row)
        return ClientEntityLinkService._serialize(row, entity=entity)

    @staticmethod
    def unlink(link_id: int) -> dict:
        """Remove a link entirely. Used to undo an approval -- rejecting
        would leave a row implying the client asked and was refused, which
        isn't what happened."""
        row = ClientEntityLinkRepository.get_by_id(link_id)
        if row is None:
            raise ClientEntityLinkError(f"No link with id {link_id}.")
        ClientEntityLinkRepository.delete(row)
        return {"removed_id": link_id}

    @staticmethod
    def clients_for_entity(entity_id: int) -> list[dict]:
        return [
            {
                "user_id": r.user_id,
                "role": r.role,
                "user_email": r.user_email,
                "user_name": " ".join(
                    p for p in (r.user_first_name, r.user_last_name) if p
                ) or None,
            }
            for r in ClientEntityLinkRepository.approved_users_for_entity(entity_id)
        ]

    # ── Shared ────────────────────────────────────────────────────────────

    @staticmethod
    def _serialize(row, entity=None) -> dict:
        entity = entity or EntityRepository.get_by_id(row.entity_id)
        return {
            "id": row.id,
            "user_id": row.user_id,
            "entity_id": row.entity_id,
            "entity_name": getattr(entity, "name", None),
            "entity_type": getattr(entity, "type", None),
            "status": row.status,
            "role": row.role,
            "note": row.note,
            "review_note": row.review_note,
            "requested_at": iso_utc(row.requested_at),
            "reviewed_at": iso_utc(row.reviewed_at),
            "reviewed_by": row.reviewed_by,
        }
