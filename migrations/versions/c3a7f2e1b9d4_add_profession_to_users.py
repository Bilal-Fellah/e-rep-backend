"""add profession to users

Revision ID: c3a7f2e1b9d4
Revises: 5d1946c976cf
Create Date: 2026-03-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a7f2e1b9d4'
down_revision = '5d1946c976cf'
branch_labels = None
depends_on = None

user_professions = sa.Enum(
    'community_manager', 'marketing', 'ceo', 'journalist',
    'influencer', 'student', 'sales', 'other',
    name='user_professions'
)


def upgrade():
    user_professions.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('profession', user_professions, nullable=True, server_default='other'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('profession')
    user_professions.drop(op.get_bind(), checkfirst=True)
