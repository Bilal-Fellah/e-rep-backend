"""add preapproved mails and subscriptions tables

Revision ID: 7c3d9a1b2e4f
Revises: f7b1a5d2c9e4
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c3d9a1b2e4f'
down_revision = 'f7b1a5d2c9e4'
branch_labels = None
depends_on = None


preapproved_mail_status = sa.Enum(
    'pending', 'used', 'revoked', 'expired', name='preapproved_mail_status'
)

subscription_status = sa.Enum(
    'pending', 'active', 'expired', 'canceled', 'revoked', name='subscription_status'
)


def upgrade():
    preapproved_mail_status.create(op.get_bind(), checkfirst=True)
    subscription_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'preapproved_mails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('status', preapproved_mail_status, nullable=False, server_default='pending'),
        sa.Column('pack_code', sa.String(length=64), nullable=False),
        sa.Column('access_rights', sa.JSON(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at', name='ck_preapproved_window'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_preapproved_mails_email'),
    )
    op.create_index(op.f('ix_preapproved_mails_email'), 'preapproved_mails', ['email'], unique=False)
    op.create_index(op.f('ix_preapproved_mails_status'), 'preapproved_mails', ['status'], unique=False)

    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', subscription_status, nullable=False, server_default='active'),
        sa.Column('pack_code', sa.String(length=64), nullable=False),
        sa.Column('access_rights', sa.JSON(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='admin'),
        sa.Column('preapproved_mail_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('ends_at IS NULL OR ends_at > starts_at', name='ck_subscriptions_window'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['preapproved_mail_id'], ['preapproved_mails.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_status'), 'subscriptions', ['status'], unique=False)
    op.create_index(op.f('ix_subscriptions_ends_at'), 'subscriptions', ['ends_at'], unique=False)
    op.create_index(op.f('ix_subscriptions_preapproved_mail_id'), 'subscriptions', ['preapproved_mail_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_subscriptions_preapproved_mail_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_ends_at'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_status'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_table('subscriptions')

    op.drop_index(op.f('ix_preapproved_mails_status'), table_name='preapproved_mails')
    op.drop_index(op.f('ix_preapproved_mails_email'), table_name='preapproved_mails')
    op.drop_table('preapproved_mails')

    subscription_status.drop(op.get_bind(), checkfirst=True)
    preapproved_mail_status.drop(op.get_bind(), checkfirst=True)
