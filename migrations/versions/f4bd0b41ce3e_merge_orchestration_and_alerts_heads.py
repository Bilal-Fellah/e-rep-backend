"""merge orchestration/scraping-provenance branch with alerts-feature branch

Revision ID: f4bd0b41ce3e
Revises: d3f9a7c1e4b5, h9i0j1k2l3m4
Create Date: 2026-08-23 09:15:00.000000

Pure merge point, no schema changes of its own. These two branches forked
after c8d4e1f6a2b7 and were developed in parallel:

  - d3f9a7c1e4b5 (via c8d4e1f6a2b7): pages_history.source/source_meta,
    scrape_attempts, scraping_profile_results
  - h9i0j1k2l3m4 (via g8h2i3j4k5l6, e5f6a7b8c9d0): alerts feature tables,
    comments.label_updated_at

Only h9i0j1k2l3m4 was ever applied to production (`flask db upgrade` only
walks one head at a time), so the d3f9a7c1e4b5 branch's tables/columns were
silently never created there -- discovered when the live own_scraper/profiles
endpoint started 500ing with "relation scraping_profile_results does not
exist" once code that actually queries it started running. This migration
just stitches the two heads back into one so `flask db upgrade` picks up
everything on both branches in one pass.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4bd0b41ce3e'
down_revision = ('d3f9a7c1e4b5', 'h9i0j1k2l3m4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
