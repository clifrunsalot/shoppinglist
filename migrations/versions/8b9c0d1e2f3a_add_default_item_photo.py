"""Add photos to default item templates."""
import sqlalchemy as sa
from alembic import op


revision = '8b9c0d1e2f3a'
down_revision = '7a8b9c0d1e2f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('default_item_templates', sa.Column('photo_url', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('default_item_templates', 'photo_url')
