"""20261030_registration_enabled

SEC-3 — self-serve registration becomes an install setting, off by default.
`POST /auth/register` used to accept anyone once an admin existed, signing the
new account straight in to the household's data; on an install reachable
through a reverse proxy that was any visitor. Existing installs get the same
closed default: the admin creates accounts on the Users page, or switches
"Let people create their own account" back on.

Revision ID: a8d3e6f1b2c9
Revises: f4b8d1c6a9e2
Create Date: 2026-10-30 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a8d3e6f1b2c9'
down_revision = 'f4b8d1c6a9e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('AppSetting') as batch:
        batch.add_column(sa.Column(
            'registration_enabled', sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ))


def downgrade():
    with op.batch_alter_table('AppSetting') as batch:
        batch.drop_column('registration_enabled')
