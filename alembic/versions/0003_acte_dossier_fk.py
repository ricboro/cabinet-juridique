"""acte: remplace many-to-many acte_dossiers par FK dossier_id directe

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Ajouter la colonne dossier_id sur actes (nullable pour la migration)
    with op.batch_alter_table("actes") as batch_op:
        batch_op.add_column(sa.Column("dossier_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_actes_dossier_id", "dossiers", ["dossier_id"], ["id"])

    # 2. Copier les données depuis acte_dossiers (un dossier par acte, on prend le premier)
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT acte_id, MIN(dossier_id) as dossier_id FROM acte_dossiers GROUP BY acte_id")
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE actes SET dossier_id = :did WHERE id = :aid"),
            {"did": row[1], "aid": row[0]},
        )

    # 3. Supprimer la table acte_dossiers
    op.drop_table("acte_dossiers")


def downgrade():
    # Recréer acte_dossiers et y réinjecter les données depuis actes.dossier_id
    op.create_table(
        "acte_dossiers",
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes.id"), primary_key=True),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers.id"), primary_key=True),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, dossier_id FROM actes WHERE dossier_id IS NOT NULL")
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text("INSERT INTO acte_dossiers (acte_id, dossier_id) VALUES (:aid, :did)"),
            {"aid": row[0], "did": row[1]},
        )

    with op.batch_alter_table("actes") as batch_op:
        batch_op.drop_constraint("fk_actes_dossier_id", type_="foreignkey")
        batch_op.drop_column("dossier_id")
