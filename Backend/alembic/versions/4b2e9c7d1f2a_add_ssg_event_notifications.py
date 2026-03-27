"""add ssg event notifications

Revision ID: 4b2e9c7d1f2a
Revises: e7b1c2d3f4ab
Create Date: 2026-03-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "4b2e9c7d1f2a"
down_revision: Union[str, None] = "e7b1c2d3f4ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("ssg_events"):
        columns = {col["name"] for col in inspector.get_columns("ssg_events")}
        if "location" not in columns:
            op.add_column("ssg_events", sa.Column("location", sa.String(length=200), nullable=True))
        if "notification_sent" not in columns:
            op.add_column(
                "ssg_events",
                sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )

    if not inspector.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("type", sa.String(length=30), nullable=False, server_default="event"),
            sa.Column("related_id", sa.Integer(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
        op.create_index("ix_notifications_school_id", "notifications", ["school_id"], unique=False)
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("notifications"):
        op.drop_index("ix_notifications_created_at", table_name="notifications")
        op.drop_index("ix_notifications_school_id", table_name="notifications")
        op.drop_index("ix_notifications_user_id", table_name="notifications")
        op.drop_table("notifications")

    if inspector.has_table("ssg_events"):
        columns = {col["name"] for col in inspector.get_columns("ssg_events")}
        with op.batch_alter_table("ssg_events") as batch_op:
            if "notification_sent" in columns:
                batch_op.drop_column("notification_sent")
            if "location" in columns:
                batch_op.drop_column("location")
