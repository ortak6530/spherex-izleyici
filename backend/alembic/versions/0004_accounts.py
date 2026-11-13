"""accounts: users, one-time login codes, sessions, saved items

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14 01:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_account")),
    )
    with op.batch_alter_table("user_account", schema=None) as b:
        b.create_index(b.f("ix_user_account_email"), ["email"], unique=True)

    op.create_table(
        "login_code",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_code")),
    )
    with op.batch_alter_table("login_code", schema=None) as b:
        b.create_index(b.f("ix_login_code_email"), ["email"], unique=False)
        b.create_index(b.f("ix_login_code_created_at"), ["created_at"], unique=False)

    op.create_table(
        "auth_session",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_auth_session")),
    )
    with op.batch_alter_table("auth_session", schema=None) as b:
        b.create_index(b.f("ix_auth_session_user_id"), ["user_id"], unique=False)
        b.create_index(b.f("ix_auth_session_expires_at"), ["expires_at"], unique=False)

    op.create_table(
        "saved_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ref", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_item")),
        sa.UniqueConstraint("user_id", "kind", "ref", name="uq_saved_item_user_kind_ref"),
    )
    with op.batch_alter_table("saved_item", schema=None) as b:
        b.create_index(b.f("ix_saved_item_user_id"), ["user_id"], unique=False)
        b.create_index(b.f("ix_saved_item_created_at"), ["created_at"], unique=False)


def downgrade() -> None:
    for table, idx in (
        ("saved_item", ["ix_saved_item_created_at", "ix_saved_item_user_id"]),
        ("auth_session", ["ix_auth_session_expires_at", "ix_auth_session_user_id"]),
        ("login_code", ["ix_login_code_created_at", "ix_login_code_email"]),
        ("user_account", ["ix_user_account_email"]),
    ):
        with op.batch_alter_table(table, schema=None) as b:
            for name in idx:
                b.drop_index(b.f(name))
        op.drop_table(table)
