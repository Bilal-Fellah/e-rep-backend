"""add alerts feature tables

Revision ID: h9i0j1k2l3m4
Revises: g8h2i3j4k5l6, e5f6a7b8c9d0
Create Date: 2026-08-21 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h9i0j1k2l3m4'
down_revision = ('g8h2i3j4k5l6', 'e5f6a7b8c9d0')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('label_updated_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_comment_label_updated_at', ['label_updated_at'], unique=False)

    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('severity_min', sa.String(length=20), nullable=True),
        sa.Column('entity_scope', sa.JSON(), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False),
        sa.Column('match_mode', sa.String(length=20), nullable=False),
        sa.Column('is_case_sensitive', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('negative_comment', 'keyword_mention', 'engagement_anomaly')",
            name='ck_alert_rule_event_type',
        ),
        sa.CheckConstraint(
            "match_mode IN ('contains', 'exact', 'regex')",
            name='ck_alert_rule_match_mode',
        ),
        sa.CheckConstraint(
            'cooldown_minutes >= 0',
            name='ck_alert_rule_cooldown_non_negative',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('alert_rules', schema=None) as batch_op:
        batch_op.create_index('ix_alert_rules_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_alert_rules_event_type', ['event_type'], unique=False)
        batch_op.create_index('ix_alert_rules_is_active', ['is_active'], unique=False)

    op.create_table(
        'alert_rule_keywords',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('keyword_normalized', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_id', 'keyword_normalized', name='uq_alert_rule_keyword_norm'),
    )
    with op.batch_alter_table('alert_rule_keywords', schema=None) as batch_op:
        batch_op.create_index('ix_alert_rule_keywords_rule_id', ['rule_id'], unique=False)
        batch_op.create_index('ix_alert_rule_keywords_keyword_normalized', ['keyword_normalized'], unique=False)

    op.create_table(
        'alert_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('dedupe_key', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('page_id', sa.String(length=36), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=True),
        sa.Column('post_id', sa.String(length=100), nullable=True),
        sa.Column('comment_pk', sa.Integer(), nullable=True),
        sa.Column('label', sa.Integer(), nullable=True),
        sa.Column('matched_keyword', sa.String(length=255), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('event_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('negative_comment', 'keyword_mention', 'engagement_anomaly')",
            name='ck_alert_event_event_type',
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'serious', 'critical')",
            name='ck_alert_event_severity',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedupe_key'),
    )
    with op.batch_alter_table('alert_events', schema=None) as batch_op:
        batch_op.create_index('ix_alert_events_event_type', ['event_type'], unique=False)
        batch_op.create_index('ix_alert_events_dedupe_key', ['dedupe_key'], unique=True)
        batch_op.create_index('ix_alert_events_severity', ['severity'], unique=False)
        batch_op.create_index('ix_alert_events_entity_id', ['entity_id'], unique=False)
        batch_op.create_index('ix_alert_events_page_id', ['page_id'], unique=False)
        batch_op.create_index('ix_alert_events_platform', ['platform'], unique=False)
        batch_op.create_index('ix_alert_events_post_id', ['post_id'], unique=False)
        batch_op.create_index('ix_alert_events_comment_pk', ['comment_pk'], unique=False)
        batch_op.create_index('ix_alert_events_event_at', ['event_at'], unique=False)

    op.create_table(
        'user_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('unread', 'read', 'dismissed')", name='ck_user_alert_status'),
        sa.ForeignKeyConstraint(['event_id'], ['alert_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'event_id', 'rule_id', name='uq_user_alert_user_event_rule'),
    )
    with op.batch_alter_table('user_alerts', schema=None) as batch_op:
        batch_op.create_index('ix_user_alerts_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_user_alerts_event_id', ['event_id'], unique=False)
        batch_op.create_index('ix_user_alerts_rule_id', ['rule_id'], unique=False)
        batch_op.create_index('ix_user_alerts_status', ['status'], unique=False)

    op.create_table(
        'alert_detector_checkpoints',
        sa.Column('detector_name', sa.String(length=80), nullable=False),
        sa.Column('cursor_ts', sa.DateTime(), nullable=True),
        sa.Column('cursor_text', sa.String(length=255), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('detector_name'),
    )


def downgrade():
    op.drop_table('alert_detector_checkpoints')

    with op.batch_alter_table('user_alerts', schema=None) as batch_op:
        batch_op.drop_index('ix_user_alerts_status')
        batch_op.drop_index('ix_user_alerts_rule_id')
        batch_op.drop_index('ix_user_alerts_event_id')
        batch_op.drop_index('ix_user_alerts_user_id')
    op.drop_table('user_alerts')

    with op.batch_alter_table('alert_events', schema=None) as batch_op:
        batch_op.drop_index('ix_alert_events_event_at')
        batch_op.drop_index('ix_alert_events_comment_pk')
        batch_op.drop_index('ix_alert_events_post_id')
        batch_op.drop_index('ix_alert_events_platform')
        batch_op.drop_index('ix_alert_events_page_id')
        batch_op.drop_index('ix_alert_events_entity_id')
        batch_op.drop_index('ix_alert_events_severity')
        batch_op.drop_index('ix_alert_events_dedupe_key')
        batch_op.drop_index('ix_alert_events_event_type')
    op.drop_table('alert_events')

    with op.batch_alter_table('alert_rule_keywords', schema=None) as batch_op:
        batch_op.drop_index('ix_alert_rule_keywords_keyword_normalized')
        batch_op.drop_index('ix_alert_rule_keywords_rule_id')
    op.drop_table('alert_rule_keywords')

    with op.batch_alter_table('alert_rules', schema=None) as batch_op:
        batch_op.drop_index('ix_alert_rules_is_active')
        batch_op.drop_index('ix_alert_rules_event_type')
        batch_op.drop_index('ix_alert_rules_user_id')
    op.drop_table('alert_rules')

    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_index('ix_comment_label_updated_at')
        batch_op.drop_column('label_updated_at')
