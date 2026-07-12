"""add name_french to categories

Revision ID: b6a7c9d4e2f1
Revises: a4c3f26a84f3
Create Date: 2026-04-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6a7c9d4e2f1'
down_revision = 'a4c3f26a84f3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('categories', sa.Column('name_french', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('categories', 'name_french')