"""add event attendance and late threshold to events

Revision ID: d5f4c3b2a1e0
Revises: c3a4d1e8b5f1
Create Date: 2026-03-13 16:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d5f4c3b2a1e0"
down_revision: Union[str, None] = "c3a4d1e8b5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("events"):
        columns = {col["name"] for col in inspector.get_columns("events")}
        if "late_threshold_minutes" not in columns:
            op.add_column(
                "events",
                sa.Column(
                    "late_threshold_minutes",
                    sa.Integer(),
                    nullable=False,
                    server_default="10",
                ),
            )

    if not inspector.has_table("event_attendance"):
        op.create_table(
            "event_attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("sign_in_time", sa.DateTime(), nullable=True),
            sa.Column("sign_out_time", sa.DateTime(), nullable=True),
            sa.Column("attendance_status", sa.String(length=20), nullable=False, server_default="absent"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("event_id", "user_id", name="uq_event_attendance_event_user"),
        )
        op.create_index("ix_event_attendance_event_id", "event_attendance", ["event_id"], unique=False)
        op.create_index("ix_event_attendance_user_id", "event_attendance", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("event_attendance"):
        op.drop_index("ix_event_attendance_user_id", table_name="event_attendance")
        op.drop_index("ix_event_attendance_event_id", table_name="event_attendance")
        op.drop_table("event_attendance")

    if inspector.has_table("events"):
        columns = {col["name"] for col in inspector.get_columns("events")}
        if "late_threshold_minutes" in columns:
            with op.batch_alter_table("events") as batch_op:
                batch_op.drop_column("late_threshold_minutes")
