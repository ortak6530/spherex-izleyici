"""feedback table

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13 23:40:00
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("page", sa.String(length=200), nullable=True),
        sa.Column("object_key", sa.String(length=120), nullable=True),
        sa.Column("release_id", sa.String(length=16), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
    )
    with op.batch_alter_table("feedback", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_feedback_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_feedback_session_id"), ["session_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_feedback_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_feedback_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_feedback_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("feedback", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_feedback_status"))
        batch_op.drop_index(batch_op.f("ix_feedback_category"))
        batch_op.drop_index(batch_op.f("ix_feedback_user_id"))
        batch_op.drop_index(batch_op.f("ix_feedback_session_id"))
        batch_op.drop_index(batch_op.f("ix_feedback_created_at"))
    op.drop_table("feedback")
