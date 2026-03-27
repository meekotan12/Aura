"""Use: Implements the database change for configurable event sign-out opening delays.
Where to use: Use this only when Alembic runs backend database upgrades or downgrades.
Role: Migration layer. It records one step in the database schema history.

add event sign out open delay minutes

Revision ID: b8e4c1d2f7a9
Revises: a6c4e2f1b9d7
Create Date: 2026-03-27 15:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b8e4c1d2f7a9"
down_revision: Union[str, None] = "a6c4e2f1b9d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {
        column["name"] for column in inspector.get_columns("events")
    }

    if "sign_out_open_delay_minutes" not in existing_columns:
        op.add_column(
            "events",
            sa.Column(
                "sign_out_open_delay_minutes",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
        op.alter_column("events", "sign_out_open_delay_minutes", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {
        column["name"] for column in inspector.get_columns("events")
    }

    if "sign_out_open_delay_minutes" in existing_columns:
        op.drop_column("events", "sign_out_open_delay_minutes")
