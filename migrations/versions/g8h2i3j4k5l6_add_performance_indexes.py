"""add performance indexes for apify fallback feature

Revision ID: g8h2i3j4k5l6
Revises: f7b1a5d2c9e4
Create Date: 2026-07-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g8h2i3j4k5l6'
down_revision = 'f7b1a5d2c9e4'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add performance indexes for apify fallback scraping feature.
    
    Key indexes:
    - pages_history.recorded_at for date range filtering (today's records)
    - pages_history.page_id for foreign key joins (verify exists)
    - pages.entity_id for entity joins (verify exists)
    - pages (entity_id, platform) composite for filtered queries
    """
    
    # Add index on pages_history.recorded_at for date range filtering
    # This enables fast "today's records" queries
    op.create_index(
        'idx_pages_history_recorded_at',
        'pages_history',
        ['recorded_at'],
        unique=False
    )
    
    # Verify/add index on pages_history.page_id for join performance
    # Foreign keys don't automatically get indexes in PostgreSQL
    op.create_index(
        'idx_pages_history_page_id',
        'pages_history',
        ['page_id'],
        unique=False
    )
    
    # Verify/add index on pages.entity_id for join performance
    op.create_index(
        'idx_pages_entity_id',
        'pages',
        ['entity_id'],
        unique=False
    )
    
    # Add composite index on pages (entity_id, platform) for filtered queries
    # This optimizes queries that filter by both entity and platform
    op.create_index(
        'idx_pages_entity_platform',
        'pages',
        ['entity_id', 'platform'],
        unique=False
    )


def downgrade():
    """
    Remove performance indexes added for apify fallback feature.
    """
    
    # Drop indexes in reverse order
    op.drop_index('idx_pages_entity_platform', table_name='pages')
    op.drop_index('idx_pages_entity_id', table_name='pages')
    op.drop_index('idx_pages_history_page_id', table_name='pages_history')
    op.drop_index('idx_pages_history_recorded_at', table_name='pages_history')
