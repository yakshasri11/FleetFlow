"""Add assignment workflow: shipment completion/dispatcher/soft-delete,
trip soft-delete, status_history, driver_locations

Revision ID: e1f4c7a9b2d3
Revises: d9a2b5c7e8f1
Create Date: 2026-08-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f4c7a9b2d3'
down_revision: Union[str, Sequence[str], None] = 'd9a2b5c7e8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('shipments') as batch_op:
        batch_op.add_column(sa.Column('dispatcher_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('completed_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('completion_note', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('completion_lat', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('completion_lng', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('deleted', sa.String(), nullable=False, server_default='false'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_shipments_dispatcher_user_id', 'users', ['dispatcher_user_id'], ['id'])
        batch_op.create_foreign_key('fk_shipments_completed_by', 'users', ['completed_by'], ['id'])
        batch_op.create_foreign_key('fk_shipments_deleted_by', 'users', ['deleted_by'], ['id'])

    with op.batch_alter_table('trips') as batch_op:
        batch_op.add_column(sa.Column('deleted', sa.String(), nullable=False, server_default='false'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_trips_deleted_by', 'users', ['deleted_by'], ['id'])

    op.create_table(
        'status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_status_history_id'), 'status_history', ['id'], unique=False)

    op.create_table(
        'driver_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=False),
        sa.Column('shipment_id', sa.Integer(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id']),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_driver_locations_id'), 'driver_locations', ['id'], unique=False)
    op.create_index('ix_driver_locations_trip_id', 'driver_locations', ['trip_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_driver_locations_trip_id', table_name='driver_locations')
    op.drop_index(op.f('ix_driver_locations_id'), table_name='driver_locations')
    op.drop_table('driver_locations')
    op.drop_index(op.f('ix_status_history_id'), table_name='status_history')
    op.drop_table('status_history')

    with op.batch_alter_table('trips') as batch_op:
        batch_op.drop_constraint('fk_trips_deleted_by', type_='foreignkey')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('deleted')

    with op.batch_alter_table('shipments') as batch_op:
        batch_op.drop_constraint('fk_shipments_deleted_by', type_='foreignkey')
        batch_op.drop_constraint('fk_shipments_completed_by', type_='foreignkey')
        batch_op.drop_constraint('fk_shipments_dispatcher_user_id', type_='foreignkey')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('deleted')
        batch_op.drop_column('completion_lng')
        batch_op.drop_column('completion_lat')
        batch_op.drop_column('completion_note')
        batch_op.drop_column('completed_by')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('dispatcher_user_id')
