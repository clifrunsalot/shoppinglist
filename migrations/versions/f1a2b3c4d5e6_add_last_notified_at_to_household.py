"""add last_notified_at to households

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-26 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = 'f1a2b3c4d5e6'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('households', sa.Column('last_notified_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('households', 'last_notified_at')
