"""Use: Implements the database change for add event late threshold minutes.
Where to use: Use this only when Alembic runs backend database upgrades or downgrades.
Role: Migration layer. It records one step in the database schema history.

add event late threshold minutes

Revision ID: b45c67d89e01
Revises: a12b34c56d78
Create Date: 2026-03-11 13:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b45c67d89e01"
down_revision: Union[str, None] = "a12b34c56d78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("events"):
        return

    columns = {column["name"] for column in inspector.get_columns("events")}
    if "late_threshold_minutes" in columns:
        return

    op.add_column(
        "events",
        sa.Column("late_threshold_minutes", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("events"):
        return

    columns = {column["name"] for column in inspector.get_columns("events")}
    if "late_threshold_minutes" not in columns:
        return

    op.drop_column("events", "late_threshold_minutes")
