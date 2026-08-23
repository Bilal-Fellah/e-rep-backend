"""add scraper credentials table

Revision ID: 3c4656dbba99
Revises: f4bd0b41ce3e
Create Date: 2026-08-23 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '3c4656dbba99'
down_revision = 'f4bd0b41ce3e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scraper_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('credential_type', sa.String(length=20), nullable=False, server_default='cookies'),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('soonest_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_check_status', sa.String(length=20), nullable=True),
        sa.Column('last_check_detail', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'credential_type', name='uq_scraper_credentials_platform_type'),
        sa.CheckConstraint("credential_type IN ('cookies')", name='ck_scraper_credentials_type'),
        sa.CheckConstraint(
            "last_check_status IS NULL OR last_check_status IN ('ok', 'auth_failed', 'error')",
            name='ck_scraper_credentials_check_status',
        ),
    )


def downgrade():
    op.drop_table('scraper_credentials')
