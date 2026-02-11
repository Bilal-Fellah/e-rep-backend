from typing import List, Optional
from sqlalchemy import or_
from datetime import datetime

from api import db
from api.models.note_model import Note


class NoteRepository:
    """Repository for Notes"""

    # ---------- Create ----------

    @staticmethod
    def create(
        *,
        author_id: int,
        content: str,
        target_type: str,
        target_id: int,
        title: Optional[str] = None,
        context_data: Optional[dict] = None,
        visibility: str = "private",
        status: str = "active",
    ) -> Note:
        note = Note(
            author_id=author_id,
            title=title,
            content=content,
            target_type=target_type,
            target_id=target_id,
            context_data=context_data,
            visibility=visibility,
            status=status,
        )

        db.session.add(note)
        db.session.commit()
        return note

    # ---------- Read ----------

    @staticmethod
    def get_by_id(note_id: int) -> Optional[Note]:
        return Note.query.filter_by(id=note_id, status="active").first()

    @staticmethod
    def get_for_target(
        *,
        target_type: str,
        target_id: int,
        user_id: int,
        include_archived: bool = False
    ) -> List[Note]:
        query = Note.query.filter(
            Note.target_type == target_type,
            Note.target_id == target_id,
        )

        if not include_archived:
            query = query.filter(Note.status == "active")

        query = query.filter(
            or_(
                Note.visibility == "public",
                Note.author_id == user_id
            )
        )

        return query.order_by(Note.created_at.desc()).all()

    @staticmethod
    def get_by_author(
        author_id: int,
        include_archived: bool = False
    ) -> List[Note]:
        query = Note.query.filter_by(author_id=author_id)

        if not include_archived:
            query = query.filter(Note.status == "active")

        return query.order_by(Note.created_at.desc()).all()

    # ---------- Update ----------

    @staticmethod
    def update(
        note: Note,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        context_data: Optional[dict] = None,
        visibility: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Note:
        if title is not None:
            note.title = title

        if content is not None:
            note.content = content

        if context_data is not None:
            note.context_data = context_data

        if visibility is not None:
            note.visibility = visibility

        if status is not None:
            note.status = status

        note.updated_at = datetime.utcnow()

        db.session.commit()
        return note

    # ---------- Delete ----------

    @staticmethod
    def soft_delete(note: Note) -> None:
        note.status = "deleted"
        note.updated_at = datetime.utcnow()
        db.session.commit()

    # ---------- Permissions ----------

    @staticmethod
    def can_view(note: Note, user_id: int) -> bool:
        if note.visibility == "public":
            return True
        return note.author_id == user_id

    @staticmethod
    def can_edit(note: Note, user_id: int) -> bool:
        return note.author_id == user_id
