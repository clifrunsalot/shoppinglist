"""add price to item

Revision ID: 8f43c8ac7d21
Revises: 342d03577063
Create Date: 2026-03-27 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f43c8ac7d21'
down_revision = '342d03577063'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_column('price')