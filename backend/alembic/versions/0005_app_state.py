"""app_state: small server values that must survive a deploy (archive freshness)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_state")),
    )


def downgrade() -> None:
    op.drop_table("app_state")
