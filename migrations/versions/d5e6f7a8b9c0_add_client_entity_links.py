"""add client entity links

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-05 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'client_entity_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'entity_id', name='uq_client_entity_links_user_entity'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')",
                           name='ck_client_entity_links_status'),
        sa.CheckConstraint("role IN ('owner', 'member')",
                           name='ck_client_entity_links_role'),
    )
    op.create_index('ix_client_entity_links_user_id', 'client_entity_links', ['user_id'])
    op.create_index('ix_client_entity_links_entity_id', 'client_entity_links', ['entity_id'])
    op.create_index('ix_client_entity_links_status', 'client_entity_links', ['status'])


def downgrade():
    op.drop_index('ix_client_entity_links_status', table_name='client_entity_links')
    op.drop_index('ix_client_entity_links_entity_id', table_name='client_entity_links')
    op.drop_index('ix_client_entity_links_user_id', table_name='client_entity_links')
    op.drop_table('client_entity_links')
