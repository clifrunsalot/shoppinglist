"""add photo url to item

Revision ID: 7a8b9c0d1e2f
Revises: f1a2b3c4d5e6
Create Date: 2026-09-04 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = '7a8b9c0d1e2f'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('items', sa.Column('photo_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('items', 'photo_url')