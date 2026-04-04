"""add users and ownership

Revision ID: 9b63b8b7c7d4
Revises: f86107bdc417
Create Date: 2026-03-28 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b63b8b7c7d4'
down_revision = 'f86107bdc417'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('stores_name_key', type_='unique')
        batch_op.create_foreign_key('fk_stores_user_id_users', 'users', ['user_id'], ['id'])
        batch_op.create_unique_constraint('uq_store_user_name', ['user_id', 'name'])

    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_items_user_id_users', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_items_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.drop_constraint('uq_store_user_name', type_='unique')
        batch_op.drop_constraint('fk_stores_user_id_users', type_='foreignkey')
        batch_op.create_unique_constraint('stores_name_key', ['name'])
        batch_op.drop_column('user_id')

    op.drop_table('users')