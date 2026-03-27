"""Use: Implements the database change for drop legacy event attendance tables.
Where to use: Use this only when Alembic runs backend database upgrades or downgrades.
Role: Migration layer. It records one step in the database schema history.

drop legacy event attendance tables

Revision ID: a6c4e2f1b9d7
Revises: f9c2d4e6a8b1
Create Date: 2026-03-25 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c4e2f1b9d7"
down_revision: Union[str, None] = "f9c2d4e6a8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_TABLES = (
    "event_attendance",
    "ssg_event_attendance",
)


def upgrade() -> None:
    for table_name in LEGACY_TABLES:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported for legacy event-attendance table cleanup."
    )
