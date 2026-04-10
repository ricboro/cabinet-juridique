"""acte is_generated + lien_onedrive nullable

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('actes', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default='0'))
    # Rendre lien_onedrive nullable (actes générés sans URL OneDrive)
    with op.batch_alter_table('actes') as batch_op:
        batch_op.alter_column('lien_onedrive', existing_type=sa.String(2000), nullable=True)


def downgrade():
    with op.batch_alter_table('actes') as batch_op:
        batch_op.alter_column('lien_onedrive', existing_type=sa.String(2000), nullable=False)
    op.drop_column('actes', 'is_generated')
