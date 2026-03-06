"""remove public and anonymous from user_roles enum

Revision ID: d4b8e3f2a1c5
Revises: c3a7f2e1b9d4
Create Date: 2026-03-06 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4b8e3f2a1c5'
down_revision = 'c3a7f2e1b9d4'
branch_labels = None
depends_on = None


def upgrade():
    # Migrate existing "public" users to "registered"
    op.execute("UPDATE users SET role = 'registered' WHERE role::text = 'public'")

    # Drop the default before changing type (it references the old enum)
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")

    # Recreate the enum without public
    op.execute("ALTER TYPE user_roles RENAME TO user_roles_old")
    new_enum = sa.Enum('registered', 'subscribed', 'admin', name='user_roles')
    new_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_roles USING role::text::user_roles"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'registered'")
    op.execute("DROP TYPE user_roles_old")


def downgrade():
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TYPE user_roles RENAME TO user_roles_old")
    old_enum = sa.Enum('public', 'registered', 'subscribed', 'admin', name='user_roles')
    old_enum.create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_roles USING role::text::user_roles"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'public'")
    op.execute("DROP TYPE user_roles_old")
