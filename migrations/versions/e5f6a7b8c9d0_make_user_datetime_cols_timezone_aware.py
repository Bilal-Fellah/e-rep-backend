"""make user datetime cols timezone-aware

Revision ID: e5f6a7b8c9d0
Revises: f7b1a5d2c9e4
Create Date: 2026-08-05 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = '7c3d9a1b2e4f'
branch_labels = None
depends_on = None


def upgrade():
    # Convert timestamp columns to timestamp with time zone.
    # Existing values are treated as UTC.
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE "
        "USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN refresh_token_exp TYPE TIMESTAMP WITH TIME ZONE "
        "USING refresh_token_exp AT TIME ZONE 'UTC'"
    )


def downgrade():
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN refresh_token_exp TYPE TIMESTAMP WITHOUT TIME ZONE"
    )
