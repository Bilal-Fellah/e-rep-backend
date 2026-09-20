# Database model definitions for client entity link model.
#
# Which client accounts belong to which company. A client asks to be added
# to a company from the app; an admin approves or rejects it in Brendex
# Admin. Nothing is linked automatically -- the request is a claim, and the
# approval is what makes it true.
#
# Many-to-many on purpose: an agency or community manager legitimately
# handles several brands, and several colleagues from one company each have
# their own login. A column on `users` would have ruled both out and needed
# a migration to undo.
#
# The link records the claim as well as the decision, so a rejected request
# stays visible rather than vanishing, and re-requesting reuses the same row
# (one row per user/entity pair) instead of piling up duplicates.
from api import db
from sqlalchemy import CheckConstraint


class ClientEntityLink(db.Model):
    __tablename__ = "client_entity_links"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id = db.Column(
        db.Integer,
        db.ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    # What this person is to the company. Advisory today -- nothing reads it
    # to make a decision -- but it's the field an access rule would need
    # later, and it costs nothing to record at approval time.
    role = db.Column(db.String(20), nullable=False, default="member")

    # The client's own words when asking ("I'm the CM for this page").
    note = db.Column(db.Text, nullable=True)
    # The admin's reason, mainly so a rejection can say why.
    review_note = db.Column(db.Text, nullable=True)

    requested_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "entity_id", name="uq_client_entity_links_user_entity"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_client_entity_links_status",
        ),
        CheckConstraint(
            "role IN ('owner', 'member')",
            name="ck_client_entity_links_role",
        ),
    )
