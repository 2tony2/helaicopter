from __future__ import annotations

import re
import unicodedata

from alembic import context, op
import sqlalchemy as sa


revision = "20260320_0010"
down_revision = "20260319_0009"
branch_labels = None
depends_on = None

_ROUTE_SLUG_MAX_LENGTH = 80
_ROUTE_SLUG_FALLBACK = "conversation"
_ROUTE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _derive_route_slug(first_message: str) -> str:
    ascii_message = unicodedata.normalize("NFKD", first_message).encode("ascii", "ignore").decode("ascii")
    slug = _ROUTE_SLUG_PATTERN.sub("-", ascii_message.lower()).strip("-")
    slug = slug[:_ROUTE_SLUG_MAX_LENGTH].strip("-")
    return slug or _ROUTE_SLUG_FALLBACK


def _existing_columns(table_name: str) -> set[str]:
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


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
    if "route_slug" not in _existing_columns("conversations"):
        op.add_column("conversations", sa.Column("route_slug", sa.Text(), nullable=True))

    updates = [
        {
            "conversation_id": row["conversation_id"],
            "route_slug": _derive_route_slug(row["first_message"]),
        }
        for row in op.get_bind()
        .execute(sa.text("SELECT conversation_id, first_message FROM conversations"))
        .mappings()
    ]
    if not updates:
        return

    op.get_bind().execute(
        sa.text(
            """
            UPDATE conversations
            SET route_slug = :route_slug
            WHERE conversation_id = :conversation_id
            """
        ),
        updates,
    )


def downgrade_oltp() -> None:
    if "route_slug" in _existing_columns("conversations"):
        op.drop_column("conversations", "route_slug")
