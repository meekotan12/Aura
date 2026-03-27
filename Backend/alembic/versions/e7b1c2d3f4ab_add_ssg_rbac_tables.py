"""add ssg rbac tables

Revision ID: e7b1c2d3f4ab
Revises: d4f6a8b0c2e4
Create Date: 2026-03-12 23:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "e7b1c2d3f4ab"
down_revision: Union[str, None] = "d4f6a8b0c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ssg_event_status') THEN
                CREATE TYPE ssg_event_status AS ENUM ('pending', 'approved', 'rejected');
            END IF;
        END $$;
        """
    )

    if not inspector.has_table("ssg_permissions"):
        op.create_table(
            "ssg_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("permission_name", sa.String(length=100), nullable=False, unique=True, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )

    if not inspector.has_table("ssg_roles"):
        op.create_table(
            "ssg_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("role_name", sa.String(length=100), nullable=False),
            sa.Column("max_members", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("school_id", "role_name", name="uq_ssg_roles_school_role"),
        )
        op.create_index("ix_ssg_roles_school_id", "ssg_roles", ["school_id"], unique=False)

    if not inspector.has_table("ssg_role_permissions"):
        op.create_table(
            "ssg_role_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["role_id"], ["ssg_roles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["permission_id"], ["ssg_permissions.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("role_id", "permission_id", name="uq_ssg_role_permission"),
        )
        op.create_index(
            "ix_ssg_role_permissions_role_id",
            "ssg_role_permissions",
            ["role_id"],
            unique=False,
        )
        op.create_index(
            "ix_ssg_role_permissions_permission_id",
            "ssg_role_permissions",
            ["permission_id"],
            unique=False,
        )

    if not inspector.has_table("ssg_user_roles"):
        op.create_table(
            "ssg_user_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("school_year", sa.String(length=20), nullable=False),
            sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_id"], ["ssg_roles.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "role_id", "school_year", name="uq_ssg_user_role_year"),
        )
        op.create_index("ix_ssg_user_roles_user_id", "ssg_user_roles", ["user_id"], unique=False)
        op.create_index("ix_ssg_user_roles_role_id", "ssg_user_roles", ["role_id"], unique=False)
        op.create_index("ix_ssg_user_roles_school_year", "ssg_user_roles", ["school_year"], unique=False)

    status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="ssg_event_status",
        create_type=False,
    )

    if not inspector.has_table("ssg_events"):
        op.create_table(
            "ssg_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("event_date", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("status", status_enum, nullable=False, server_default="pending"),
            sa.Column("approved_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ssg_events_school_id", "ssg_events", ["school_id"], unique=False)
        op.create_index("ix_ssg_events_status", "ssg_events", ["status"], unique=False)
        op.create_index("ix_ssg_events_event_date", "ssg_events", ["event_date"], unique=False)

    if not inspector.has_table("ssg_announcements"):
        op.create_table(
            "ssg_announcements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("school_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=150), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ssg_announcements_school_id", "ssg_announcements", ["school_id"], unique=False)

    op.execute(
        """
        INSERT INTO ssg_permissions (permission_name, created_at)
        VALUES
            ('post_announcement', NOW()),
            ('create_event', NOW()),
            ('approve_event', NOW()),
            ('edit_event', NOW()),
            ('delete_event', NOW())
        ON CONFLICT (permission_name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ssg_announcements_school_id", table_name="ssg_announcements")
    op.drop_table("ssg_announcements")

    op.drop_index("ix_ssg_events_event_date", table_name="ssg_events")
    op.drop_index("ix_ssg_events_status", table_name="ssg_events")
    op.drop_index("ix_ssg_events_school_id", table_name="ssg_events")
    op.drop_table("ssg_events")

    op.drop_index("ix_ssg_user_roles_school_year", table_name="ssg_user_roles")
    op.drop_index("ix_ssg_user_roles_role_id", table_name="ssg_user_roles")
    op.drop_index("ix_ssg_user_roles_user_id", table_name="ssg_user_roles")
    op.drop_table("ssg_user_roles")

    op.drop_index("ix_ssg_role_permissions_permission_id", table_name="ssg_role_permissions")
    op.drop_index("ix_ssg_role_permissions_role_id", table_name="ssg_role_permissions")
    op.drop_table("ssg_role_permissions")

    op.drop_index("ix_ssg_roles_school_id", table_name="ssg_roles")
    op.drop_table("ssg_roles")

    op.drop_table("ssg_permissions")

    op.execute("DROP TYPE IF EXISTS ssg_event_status")
