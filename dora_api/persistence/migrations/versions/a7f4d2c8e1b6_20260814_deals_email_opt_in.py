"""20260814_deals_email_opt_in

Owner report 2026-08-14 — "Weekly deals is default on even if the email system
isn't set up yet." Not dev data: `User.deals_email_enabled` shipped with
`server_default=true()`, so every new user landed pre-subscribed to the weekly
deals email. On a fresh install there is no SMTP, so that is mail the server
cannot send — and the Notifications toggle is `:disable`d while SMTP is
unconfigured, so the user could not even turn it off.

Flips the column to opt-in, matching its sibling `alerts_email_enabled`
(`False` — "channels: in-app on; email off (opt-in)", PROPOSAL_ALERTS §5).
`send_deals_on_day` is untouched, so a user who opts in still gets their
preferred day back.

**Pre-release hard change — existing subscriptions are not preserved:** rows
currently set to True are reset to False. Pre-release, "subscribed" state that
nobody consciously chose isn't worth carrying, and leaving it True would keep
the exact surprise this fixes. Anyone who wants the email opts in on
Settings → Notifications.

Revision ID: a7f4d2c8e1b6
Revises: e2b7c9f4a6d1
Create Date: 2026-08-14 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


revision = 'a7f4d2c8e1b6'
down_revision = 'e2b7c9f4a6d1'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite can't ALTER a default in place; batch mode recreates the table.
    with op.batch_alter_table('User') as batch_op:
        batch_op.alter_column(
            'deals_email_enabled',
            existing_type = sa.Boolean(),
            existing_nullable = False,
            server_default = sa.false(),
        )
    # `sa.false()` renders `0` on SQLite and `false` on Postgres (a boolean
    # column there rejects the integer literal).
    user = sa.table('User', sa.column('deals_email_enabled', sa.Boolean()))
    op.execute(user.update().values(deals_email_enabled=sa.false()))


def downgrade():
    with op.batch_alter_table('User') as batch_op:
        batch_op.alter_column(
            'deals_email_enabled',
            existing_type = sa.Boolean(),
            existing_nullable = False,
            server_default = sa.true(),
        )
