"""create metrics table

Revision ID: ca6e5c5586b0
Revises: 4bf420e833e7
Create Date: 2026-10-11 20:28:51.676292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca6e5c5586b0'
down_revision: Union[str, Sequence[str], None] = '4bf420e833e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('metrics',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_id', sa.BigInteger(), nullable=False),
    sa.Column('metric', sa.Text(), nullable=False),
    sa.Column('value', sa.Numeric(), nullable=False),
    sa.Column('ingest_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id']),
    sa.PrimaryKeyConstraint('event_id', 'event_time')
    )
    op.create_index('ix_metrics_source_id_metric_event_time', 'metrics', ['source_id', 'metric', 'event_time'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_metrics_source_id_metric_event_time', table_name='metrics')
    op.drop_table('metrics')