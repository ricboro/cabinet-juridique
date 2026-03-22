"""statut suspendu -> transfere

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('dossiers') as batch_op:
        batch_op.alter_column(
            'statut',
            type_=sa.Enum('en_cours', 'cloture', 'transfere', name='dossier_statut'),
            existing_type=sa.Enum('en_cours', 'cloture', 'suspendu', name='dossier_statut'),
        )
    op.execute("UPDATE dossiers SET statut = 'transfere' WHERE statut = 'suspendu'")


def downgrade():
    op.execute("UPDATE dossiers SET statut = 'suspendu' WHERE statut = 'transfere'")
    with op.batch_alter_table('dossiers') as batch_op:
        batch_op.alter_column(
            'statut',
            type_=sa.Enum('en_cours', 'cloture', 'suspendu', name='dossier_statut'),
            existing_type=sa.Enum('en_cours', 'cloture', 'transfere', name='dossier_statut'),
        )
