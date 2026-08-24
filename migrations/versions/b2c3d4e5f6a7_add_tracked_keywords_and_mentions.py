"""add tracked keywords and keyword mentions tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-24 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tracked_keywords',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False, server_default='tiktok'),
        sa.Column('keyword', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'platform', 'keyword', name='uq_tracked_keywords_user_platform_keyword'
        ),
    )
    op.create_index('ix_tracked_keywords_user_id', 'tracked_keywords', ['user_id'])

    op.create_table(
        'keyword_mentions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('keyword_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('video_id', sa.String(length=64), nullable=False),
        sa.Column('video_url', sa.Text(), nullable=False),
        sa.Column('author_username', sa.String(length=120), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=True),
        sa.Column('comment_count', sa.Integer(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['keyword_id'], ['tracked_keywords.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('keyword_id', 'video_id', name='uq_keyword_mentions_keyword_video'),
    )
    op.create_index('ix_keyword_mentions_keyword_id', 'keyword_mentions', ['keyword_id'])


def downgrade():
    op.drop_index('ix_keyword_mentions_keyword_id', table_name='keyword_mentions')
    op.drop_table('keyword_mentions')
    op.drop_index('ix_tracked_keywords_user_id', table_name='tracked_keywords')
    op.drop_table('tracked_keywords')
