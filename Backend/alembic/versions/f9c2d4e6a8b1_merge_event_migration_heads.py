"""merge event migration heads

Revision ID: f9c2d4e6a8b1
Revises: b1a2c3d4e5f6, d5f4c3b2a1e0
Create Date: 2026-03-22 00:00:00.000000
"""

from typing import Sequence, Union


revision: str = "f9c2d4e6a8b1"
down_revision: Union[str, Sequence[str], None] = ("b1a2c3d4e5f6", "d5f4c3b2a1e0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
