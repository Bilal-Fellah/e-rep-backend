# Database model definitions for data correction model.
#
# Append-only audit log of manual admin fixes to otherwise-scraped data.
# Never updated or deleted in place — each row is a permanent record of
# "who changed what, from what, to what, and why". See
# api/services/correction_service.py for the whitelist of what can be
# corrected and how corrections are actually applied.
from api import db
from sqlalchemy import CheckConstraint


class DataCorrection(db.Model):
    __tablename__ = "data_corrections"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # What was corrected. target_id is stored as text so it can hold an
    # int (entities.id, pages_history.id), a uuid (pages.uuid), or a
    # composite "<pages_history.id>:<post_id>" (post_metric) without a
    # polymorphic FK.
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Text, nullable=False)
    field = db.Column(db.String(100), nullable=False)

    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            target_type.in_(["entity", "page", "page_history", "post_metric"]),
            name="ck_data_corrections_target_type",
        ),
    )
