"""Add document size_bytes and error_message.

Revision ID: 0003_document_metadata
Revises: 0002_usage_columns
Create Date: 2026-07-15

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_document_metadata"
down_revision: Union[str, Sequence[str], None] = "0002_usage_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "size_bytes")
