"""client representant legal (societe)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('representant_nom', sa.String(100), nullable=True))
    op.add_column('clients', sa.Column('representant_prenom', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('clients', 'representant_prenom')
    op.drop_column('clients', 'representant_nom')
