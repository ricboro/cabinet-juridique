"""client source provenance

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients') as batch_op:
        batch_op.add_column(sa.Column('source_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('source_detail', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('source_client_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('clients') as batch_op:
        batch_op.drop_column('source_client_id')
        batch_op.drop_column('source_detail')
        batch_op.drop_column('source_type')
