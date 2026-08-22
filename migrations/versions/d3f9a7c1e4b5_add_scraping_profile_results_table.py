"""add scraping profile results table

Revision ID: d3f9a7c1e4b5
Revises: c8d4e1f6a2b7
Create Date: 2026-08-21 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f9a7c1e4b5'
down_revision = 'c8d4e1f6a2b7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scraping_profile_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('account_id', sa.String(length=64), nullable=False),
        sa.Column('scraping_session_id', sa.String(length=36), nullable=True),
        sa.Column('profile_inserted', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['scraping_session_id'], ['scraping_sessions.session_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('page_id', 'platform', 'scraping_session_id', name='uq_scraping_profile_result'),
    )
    op.create_index('ix_spfr_page_lookup', 'scraping_profile_results', ['page_id', 'platform'], unique=False)
    op.create_index('ix_spfr_scraped_at', 'scraping_profile_results', ['scraped_at'], unique=False)
    op.create_index('ix_spfr_session', 'scraping_profile_results', ['scraping_session_id'], unique=False)


def downgrade():
    op.drop_index('ix_spfr_session', table_name='scraping_profile_results')
    op.drop_index('ix_spfr_scraped_at', table_name='scraping_profile_results')
    op.drop_index('ix_spfr_page_lookup', table_name='scraping_profile_results')
    op.drop_table('scraping_profile_results')
