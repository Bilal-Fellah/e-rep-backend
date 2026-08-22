# Database model definitions for page history model.
from api import db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID


class PageHistory(db.Model):
    __tablename__ = "pages_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data = db.Column(JSONB, nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    page_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("pages.uuid",ondelete='CASCADE',
        onupdate='CASCADE')
        )

    # Provenance of this snapshot, added for the Bright Data / Apify / own-
    # scraper orchestration flow (see api/services/scrape_orchestrator_service.py).
    # Nullable so every historical row written before this column existed
    # stays valid — a NULL source means "unknown / pre-orchestration", not
    # an error. `source` is the primary contributor (usually the primary
    # source, or the last source that had to fill a gap); `source_meta`
    # records the full per-field breakdown plus cost when more than one
    # source contributed to a single snapshot.
    source = db.Column(db.String(20), nullable=True)
    source_meta = db.Column(JSONB, nullable=True)

    # relationship to Page (optional, if you want ORM navigation)
    page = relationship("Page", back_populates="histories", foreign_keys=[page_id])
