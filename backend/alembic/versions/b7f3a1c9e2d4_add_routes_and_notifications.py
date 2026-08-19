"""Add routes and notifications tables

Revision ID: b7f3a1c9e2d4
Revises: dac58db9bd77
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f3a1c9e2d4'
down_revision: Union[str, Sequence[str], None] = 'dac58db9bd77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'routes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trip_id', sa.Integer(), nullable=True),
        sa.Column('origin', sa.String(), nullable=False),
        sa.Column('destination', sa.String(), nullable=False),
        sa.Column('origin_lat', sa.Float(), nullable=True),
        sa.Column('origin_lng', sa.Float(), nullable=True),
        sa.Column('destination_lat', sa.Float(), nullable=True),
        sa.Column('destination_lng', sa.Float(), nullable=True),
        sa.Column('route_type', sa.Enum('SHORTEST', 'FASTEST', 'TRAFFIC_AVOIDANCE', 'FUEL_EFFICIENT', name='routetype'), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('duration_minutes', sa.Float(), nullable=True),
        sa.Column('traffic_delay_minutes', sa.Float(), nullable=True),
        sa.Column('is_estimated', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('recalculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routes_id'), 'routes', ['id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.Enum('ADMIN', 'FLEET_MANAGER', 'DRIVER', 'DISPATCHER', name='userrole'), nullable=True),
        sa.Column('type', sa.Enum('MAINTENANCE_ALERT', 'DELIVERY_UPDATE', 'DRIVER_ASSIGNMENT', 'SHIPMENT_STATUS', 'ROUTE_CHANGE', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('related_entity_type', sa.String(), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_routes_id'), table_name='routes')
    op.drop_table('routes')
    sa.Enum(name='notificationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='routetype').drop(op.get_bind(), checkfirst=True)
