"""Échéances multiples par dossier (supprime date_echeance et date_audience)

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # Créer la table echeances
    op.create_table(
        'echeances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dossier_id', sa.Integer(), nullable=False),
        sa.Column('libelle', sa.String(200), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Migrer date_echeance et date_audience existantes en échéances
    op.execute("""
        INSERT INTO echeances (dossier_id, libelle, date)
        SELECT id, 'Échéance', date_echeance
        FROM dossiers
        WHERE date_echeance IS NOT NULL
    """)
    op.execute("""
        INSERT INTO echeances (dossier_id, libelle, date)
        SELECT id, 'Audience', date_audience
        FROM dossiers
        WHERE date_audience IS NOT NULL
    """)

    # Supprimer les colonnes obsolètes (SQLite : recréer la table)
    with op.batch_alter_table('dossiers') as batch_op:
        batch_op.drop_column('date_echeance')
        batch_op.drop_column('date_audience')


def downgrade():
    with op.batch_alter_table('dossiers') as batch_op:
        batch_op.add_column(sa.Column('date_echeance', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('date_audience', sa.Date(), nullable=True))
    op.drop_table('echeances')
