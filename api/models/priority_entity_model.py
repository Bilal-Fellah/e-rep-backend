# Database model definitions for priority entity model.
#
# The "priority" list: the handful of entities belonging to paying clients,
# which get a stricter standard of care than the rest of the database. Being
# on this list doesn't change how anything is scraped -- it changes how
# closely an admin watches it: the Priority page in Brendex Admin runs a
# deeper per-page validity check over these entities than the fleet-wide
# Data Integrity report does, and lets an admin fire a scrape for one of
# them and then verify that the client's own pages actually got fresh data.
#
# Deliberately a separate table rather than a flag on `entities`: who is
# paying is an operational/commercial fact with its own provenance (who
# added it, when, why), not an attribute of the brand itself, and it must
# not leak into any client-facing entity payload.
from api import db


class PriorityEntity(db.Model):
    __tablename__ = "priority_entities"

    id = db.Column(db.Integer, primary_key=True)

    # One row per entity -- the list is a set, not a log.
    entity_id = db.Column(
        db.Integer,
        db.ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Free-text, admin-facing only: the client/contract this entity is
    # covered by ("Djezzy - annual", "pilot"). Not parsed anywhere.
    label = db.Column(db.String(80), nullable=True)
    note = db.Column(db.Text, nullable=True)

    added_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
