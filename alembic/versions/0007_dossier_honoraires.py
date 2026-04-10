"""dossier honoraire_horaire estimation_heures

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dossiers', sa.Column('honoraire_horaire', sa.Float(), nullable=True))
    op.add_column('dossiers', sa.Column('estimation_heures', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('dossiers', 'estimation_heures')
    op.drop_column('dossiers', 'honoraire_horaire')
