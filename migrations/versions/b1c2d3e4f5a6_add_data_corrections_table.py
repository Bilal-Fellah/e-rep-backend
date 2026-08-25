"""add data corrections table

Revision ID: b1c2d3e4f5a6
Revises: 7c3d9a1b2e4f
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = '7c3d9a1b2e4f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'data_corrections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=True),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_id', sa.Text(), nullable=False),
        sa.Column('field', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "target_type IN ('entity', 'page', 'page_history', 'post_metric')",
            name='ck_data_corrections_target_type',
        ),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_data_corrections_target_type'), 'data_corrections', ['target_type'], unique=False)
    op.create_index(
        'ix_data_corrections_target_type_target_id',
        'data_corrections',
        ['target_type', 'target_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_data_corrections_target_type_target_id', table_name='data_corrections')
    op.drop_index(op.f('ix_data_corrections_target_type'), table_name='data_corrections')
    op.drop_table('data_corrections')
