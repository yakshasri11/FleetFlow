"""Add driver_id and is_active to users

Revision ID: c4d8e6f1a3b5
Revises: b7f3a1c9e2d4
Create Date: 2026-08-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d8e6f1a3b5'
down_revision: Union[str, Sequence[str], None] = 'b7f3a1c9e2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('driver_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_active', sa.String(), nullable=False, server_default='true'))
        batch_op.create_foreign_key('fk_users_driver_id', 'drivers', ['driver_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_driver_id', type_='foreignkey')
        batch_op.drop_column('is_active')
        batch_op.drop_column('driver_id')
