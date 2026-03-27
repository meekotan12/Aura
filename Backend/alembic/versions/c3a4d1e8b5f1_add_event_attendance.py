"""add event attendance tracking

Revision ID: c3a4d1e8b5f1
Revises: 4b2e9c7d1f2a
Create Date: 2026-03-13 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c3a4d1e8b5f1"
down_revision: Union[str, None] = "4b2e9c7d1f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("ssg_events"):
        columns = {col["name"] for col in inspector.get_columns("ssg_events")}
        if "start_time" not in columns:
            op.add_column(
                "ssg_events",
                sa.Column(
                    "start_time",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("NOW()"),
                ),
            )
        if "end_time" not in columns:
            op.add_column(
                "ssg_events",
                sa.Column(
                    "end_time",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("NOW()"),
                ),
            )
        if "late_threshold_minutes" not in columns:
            op.add_column(
                "ssg_events",
                sa.Column(
                    "late_threshold_minutes",
                    sa.Integer(),
                    nullable=False,
                    server_default="10",
                ),
            )

    if not inspector.has_table("ssg_event_attendance"):
        op.create_table(
            "ssg_event_attendance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("sign_in_time", sa.DateTime(), nullable=True),
            sa.Column("sign_out_time", sa.DateTime(), nullable=True),
            sa.Column("attendance_status", sa.String(length=20), nullable=False, server_default="absent"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["event_id"], ["ssg_events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("event_id", "user_id", name="uq_ssg_event_attendance_event_user"),
        )
        op.create_index("ix_ssg_event_attendance_event_id", "ssg_event_attendance", ["event_id"], unique=False)
        op.create_index("ix_ssg_event_attendance_user_id", "ssg_event_attendance", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("ssg_event_attendance"):
        op.drop_index("ix_ssg_event_attendance_user_id", table_name="ssg_event_attendance")
        op.drop_index("ix_ssg_event_attendance_event_id", table_name="ssg_event_attendance")
        op.drop_table("ssg_event_attendance")

    if inspector.has_table("ssg_events"):
        columns = {col["name"] for col in inspector.get_columns("ssg_events")}
        with op.batch_alter_table("ssg_events") as batch_op:
            if "late_threshold_minutes" in columns:
                batch_op.drop_column("late_threshold_minutes")
            if "end_time" in columns:
                batch_op.drop_column("end_time")
            if "start_time" in columns:
                batch_op.drop_column("start_time")
