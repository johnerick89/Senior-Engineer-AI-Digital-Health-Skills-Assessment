"""Add usage cost columns and usage_events ledger.

Revision ID: 0002_usage_columns
Revises: 0001_initial_rag_schema
Create Date: 2026-07-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_usage_columns"
down_revision: Union[str, Sequence[str], None] = "0001_initial_rag_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "chat_messages", sa.Column("completion_tokens", sa.Integer(), nullable=True)
    )
    op.add_column("chat_messages", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "chat_messages",
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=True),
    )
    op.add_column("chat_messages", sa.Column("model", sa.Text(), nullable=True))

    op.add_column(
        "document_chunks", sa.Column("prompt_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_chunks",
        sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=True),
    )
    op.add_column("document_chunks", sa.Column("model", sa.Text(), nullable=True))

    op.create_table(
        "usage_events",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "completion_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(12, 8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("thread_id", sa.UUID(), nullable=True),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("chunk_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["chat_threads.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "kind IN ("
            "'suggestion', 'chat_completion', 'query_embedding', 'ingest_embedding'"
            ")",
            name="ck_usage_events_kind",
        ),
    )
    op.create_index("ix_usage_events_kind", "usage_events", ["kind"])
    op.create_index("ix_usage_events_thread_id", "usage_events", ["thread_id"])
    op.create_index("ix_usage_events_message_id", "usage_events", ["message_id"])
    op.create_index("ix_usage_events_document_id", "usage_events", ["document_id"])
    op.create_index("ix_usage_events_chunk_id", "usage_events", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_chunk_id", table_name="usage_events")
    op.drop_index("ix_usage_events_document_id", table_name="usage_events")
    op.drop_index("ix_usage_events_message_id", table_name="usage_events")
    op.drop_index("ix_usage_events_thread_id", table_name="usage_events")
    op.drop_index("ix_usage_events_kind", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_column("document_chunks", "model")
    op.drop_column("document_chunks", "estimated_cost_usd")
    op.drop_column("document_chunks", "prompt_tokens")

    op.drop_column("chat_messages", "model")
    op.drop_column("chat_messages", "estimated_cost_usd")
    op.drop_column("chat_messages", "total_tokens")
    op.drop_column("chat_messages", "completion_tokens")
    op.drop_column("chat_messages", "prompt_tokens")
