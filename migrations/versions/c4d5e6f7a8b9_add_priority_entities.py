"""add priority entities table and entity tag on scrape trigger requests

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'priority_entities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_id', name='uq_priority_entities_entity_id'),
    )
    op.create_index('ix_priority_entities_entity_id', 'priority_entities', ['entity_id'])

    # Which priority client a manual trigger was fired for, when it was
    # fired from the Priority page. Purely provenance: the VPS watcher
    # ignores it (a run is still platform-wide), but it's what lets the
    # Priority page say "this run was queued for Djezzy at 14:02" and then
    # verify that Djezzy's own pages actually got fresh data afterwards.
    op.add_column(
        'scrape_trigger_requests',
        sa.Column('entity_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_scrape_trigger_requests_entity_id',
        'scrape_trigger_requests',
        'entities',
        ['entity_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint(
        'fk_scrape_trigger_requests_entity_id', 'scrape_trigger_requests', type_='foreignkey'
    )
    op.drop_column('scrape_trigger_requests', 'entity_id')

    op.drop_index('ix_priority_entities_entity_id', table_name='priority_entities')
    op.drop_table('priority_entities')
