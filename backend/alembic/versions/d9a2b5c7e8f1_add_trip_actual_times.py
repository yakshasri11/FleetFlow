"""Add actual trip timestamps for driver workflow

Revision ID: d9a2b5c7e8f1
Revises: c4d8e6f1a3b5
Create Date: 2026-08-16 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9a2b5c7e8f1'
down_revision: Union[str, Sequence[str], None] = 'c4d8e6f1a3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('actual_start', sa.DateTime(), nullable=True))
    op.add_column('trips', sa.Column('actual_arrival', sa.DateTime(), nullable=True))
    op.add_column('trips', sa.Column('actual_end', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'actual_end')
    op.drop_column('trips', 'actual_arrival')
    op.drop_column('trips', 'actual_start')
