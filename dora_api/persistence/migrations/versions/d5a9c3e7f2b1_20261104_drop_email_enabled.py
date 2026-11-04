"""20261104_drop_email_enabled

`AppSetting.email_enabled` dropped (FU-906, owner: delete redundant settings).
Nothing ever read it: every mail Dora sends goes out as soon as an SMTP
username is set (`email_sender` dry-runs without one), so the "Email enabled"
toggle switched nothing on or off. The SMTP username is the real control, and
`/api/health features.email_smtp_configured` already reports it.

Revision ID: d5a9c3e7f2b1
Revises: c8f3a6e2d9b4
Create Date: 2026-11-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'd5a9c3e7f2b1'
down_revision = 'c8f3a6e2d9b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('AppSetting') as batch:
        batch.drop_column('email_enabled')


def downgrade():
    with op.batch_alter_table('AppSetting') as batch:
        batch.add_column(sa.Column(
            'email_enabled', sa.Boolean(), nullable=False, server_default=sa.false(),
        ))
