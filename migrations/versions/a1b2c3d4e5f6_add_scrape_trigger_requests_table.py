"""add scrape trigger requests table

Revision ID: a1b2c3d4e5f6
Revises: 3c4656dbba99
Create Date: 2026-08-24 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3c4656dbba99'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scrape_trigger_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('requested_by', sa.Integer(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name='ck_scrape_trigger_requests_status',
        ),
    )
    op.create_index(
        'ix_scrape_trigger_requests_status_requested_at',
        'scrape_trigger_requests',
        ['status', 'requested_at'],
    )


def downgrade():
    op.drop_index('ix_scrape_trigger_requests_status_requested_at', table_name='scrape_trigger_requests')
    op.drop_table('scrape_trigger_requests')
