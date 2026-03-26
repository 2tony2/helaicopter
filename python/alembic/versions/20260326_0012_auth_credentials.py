from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20260326_0012"
down_revision = "20260326_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    upgrade_oltp()


def downgrade() -> None:
    target = context.get_x_argument(as_dictionary=True).get("target", "oltp")
    if target != "oltp":
        return
    downgrade_oltp()


def upgrade_oltp() -> None:
    op.create_table(
        "auth_credentials",
        sa.Column("credential_id", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("credential_type", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oauth_scopes_json", sa.Text(), nullable=True),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("cli_config_path", sa.Text(), nullable=True),
        sa.Column("subscription_id", sa.Text(), nullable=True),
        sa.Column("subscription_tier", sa.Text(), nullable=True),
        sa.Column("rate_limit_tier", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cumulative_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cost_since_reset", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.create_index("ix_auth_credentials_provider", "auth_credentials", ["provider"])
    op.create_index("ix_auth_credentials_status", "auth_credentials", ["status"])

    # Add FK from worker_registry to auth_credentials
    with op.batch_alter_table("worker_registry") as batch_op:
        batch_op.create_foreign_key(
            "fk_worker_registry_auth_credential_id",
            "auth_credentials",
            ["auth_credential_id"],
            ["credential_id"],
        )


def downgrade_oltp() -> None:
    with op.batch_alter_table("worker_registry") as batch_op:
        batch_op.drop_constraint("fk_worker_registry_auth_credential_id", type_="foreignkey")
    op.drop_index("ix_auth_credentials_status", table_name="auth_credentials")
    op.drop_index("ix_auth_credentials_provider", table_name="auth_credentials")
    op.drop_table("auth_credentials")
