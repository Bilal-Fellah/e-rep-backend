"""add scraping_post_results table

Revision ID: f1a2b3c4d5e6
Revises: 4798ca7d86eb
Create Date: 2026-07-14 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '4798ca7d86eb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scraping_post_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('page_id', sa.String(length=36), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('post_id', sa.String(length=100), nullable=False),
        sa.Column('scraping_session_id', sa.String(length=36), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['scraping_session_id'],
            ['scraping_sessions.session_id'],
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'page_id', 'platform', 'post_id', 'scraping_session_id',
            name='uq_scraping_post_result'
        ),
    )
    with op.batch_alter_table('scraping_post_results', schema=None) as batch_op:
        batch_op.create_index('ix_spr_post_lookup', ['page_id', 'platform', 'post_id'], unique=False)
        batch_op.create_index('ix_spr_scraped_at', ['scraped_at'], unique=False)
        batch_op.create_index('ix_spr_session', ['scraping_session_id'], unique=False)


def downgrade():
    with op.batch_alter_table('scraping_post_results', schema=None) as batch_op:
        batch_op.drop_index('ix_spr_session')
        batch_op.drop_index('ix_spr_scraped_at')
        batch_op.drop_index('ix_spr_post_lookup')

    op.drop_table('scraping_post_results')
