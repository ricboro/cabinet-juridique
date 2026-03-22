"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "avocats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("prenom", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("personne", "societe", name="client_type"),
            nullable=False,
        ),
        sa.Column("nom", sa.String(100), nullable=True),
        sa.Column("prenom", sa.String(100), nullable=True),
        sa.Column("raison_sociale", sa.String(200), nullable=True),
        sa.Column("siret", sa.String(14), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("telephone", sa.String(20), nullable=True),
        sa.Column("adresse", sa.Text(), nullable=True),
        sa.Column("date_creation", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dossiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(20), nullable=False),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("contexte", sa.Text(), nullable=True),
        sa.Column(
            "statut",
            sa.Enum("en_cours", "cloture", "suspendu", name="dossier_statut"),
            nullable=True,
        ),
        sa.Column("date_ouverture", sa.Date(), nullable=False),
        sa.Column("date_cloture", sa.Date(), nullable=True),
        sa.Column("date_echeance", sa.Date(), nullable=True),
        sa.Column("date_audience", sa.Date(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("avocat_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["avocat_id"], ["avocats.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )

    op.create_table(
        "type_actes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("libelle"),
    )

    op.create_table(
        "actes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(300), nullable=False),
        sa.Column("type_acte_id", sa.Integer(), nullable=False),
        sa.Column("lien_onedrive", sa.String(2000), nullable=False),
        sa.Column("date_production", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["type_acte_id"], ["type_actes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("libelle"),
    )

    op.create_table(
        "acte_dossiers",
        sa.Column("acte_id", sa.Integer(), nullable=False),
        sa.Column("dossier_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["acte_id"], ["actes.id"]),
        sa.ForeignKeyConstraint(["dossier_id"], ["dossiers.id"]),
        sa.PrimaryKeyConstraint("acte_id", "dossier_id"),
    )

    op.create_table(
        "acte_tags",
        sa.Column("acte_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["acte_id"], ["actes.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
        sa.PrimaryKeyConstraint("acte_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("acte_tags")
    op.drop_table("acte_dossiers")
    op.drop_table("tags")
    op.drop_table("actes")
    op.drop_table("type_actes")
    op.drop_table("dossiers")
    op.drop_table("clients")
    op.drop_table("avocats")
