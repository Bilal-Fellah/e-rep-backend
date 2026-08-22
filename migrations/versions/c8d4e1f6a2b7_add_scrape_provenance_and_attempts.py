"""add scrape provenance columns and scrape_attempts table

Revision ID: c8d4e1f6a2b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c8d4e1f6a2b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Provenance columns on pages_history — both nullable, so every row
    # written before this migration (i.e. everything the scraper has ever
    # loaded out-of-band so far) stays valid with source=NULL rather than
    # needing a backfill.
    op.add_column('pages_history', sa.Column('source', sa.String(length=20), nullable=True))
    op.add_column('pages_history', sa.Column('source_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table(
        'scrape_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('domain', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('primary_source', sa.String(length=20), nullable=False),
        sa.Column('primary_status', sa.String(length=20), nullable=False),
        sa.Column('primary_missing_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fallback_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('final_status', sa.String(length=20), nullable=False),
        sa.Column('final_missing_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('pages_history_id', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.CheckConstraint("domain IN ('profile', 'posts')", name='ck_scrape_attempts_domain'),
        sa.CheckConstraint(
            "primary_status IN ('complete', 'partial', 'failed')",
            name='ck_scrape_attempts_primary_status',
        ),
        sa.CheckConstraint(
            "final_status IN ('complete', 'partial', 'failed')",
            name='ck_scrape_attempts_final_status',
        ),
        sa.ForeignKeyConstraint(['page_id'], ['pages.uuid'], ondelete='CASCADE', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['pages_history_id'], ['pages_history.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scrape_attempts_page_id'), 'scrape_attempts', ['page_id'], unique=False)
    op.create_index(
        'ix_scrape_attempts_platform_domain_started_at',
        'scrape_attempts',
        ['platform', 'domain', 'started_at'],
        unique=False,
    )
    op.create_index(op.f('ix_scrape_attempts_final_status'), 'scrape_attempts', ['final_status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_scrape_attempts_final_status'), table_name='scrape_attempts')
    op.drop_index('ix_scrape_attempts_platform_domain_started_at', table_name='scrape_attempts')
    op.drop_index(op.f('ix_scrape_attempts_page_id'), table_name='scrape_attempts')
    op.drop_table('scrape_attempts')
    op.drop_column('pages_history', 'source_meta')
    op.drop_column('pages_history', 'source')
