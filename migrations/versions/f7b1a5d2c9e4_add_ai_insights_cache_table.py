"""add ai insights cache table

Revision ID: f7b1a5d2c9e4
Revises: 60e26b2b35be
Create Date: 2026-07-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7b1a5d2c9e4'
down_revision = '60e26b2b35be'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_insights_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(length=64), nullable=False),
        sa.Column('view_type', sa.String(length=50), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_insights_cache_cache_key'), 'ai_insights_cache', ['cache_key'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_ai_insights_cache_cache_key'), table_name='ai_insights_cache')
    op.drop_table('ai_insights_cache')
