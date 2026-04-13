"""add default category templates

Revision ID: 1d2d3c4b5e6f
Revises: 3c6a0bb190a1
Create Date: 2026-04-12 23:10:00.000000

"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d2d3c4b5e6f'
down_revision = '3c6a0bb190a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'default_category_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_default_category_template_name'),
        sa.UniqueConstraint('template_key'),
    )

    bind = op.get_bind()
    metadata = sa.MetaData()
    default_category_templates = sa.Table('default_category_templates', metadata, autoload_with=bind)
    default_item_templates = sa.Table('default_item_templates', metadata, autoload_with=bind)
    items = sa.Table('items', metadata, autoload_with=bind)

    category_names = {}
    category_rows = list(bind.execute(sa.select(default_item_templates.c.category)).fetchall())
    category_rows.extend(bind.execute(sa.select(items.c.category)).fetchall())

    for (raw_name,) in category_rows:
        normalized_name = (raw_name or '').strip()
        if not normalized_name:
            continue
        category_names.setdefault(normalized_name.lower(), normalized_name)

    for category_name in sorted(category_names.values(), key=lambda value: value.lower()):
        bind.execute(
            default_category_templates.insert().values(
                template_key=str(uuid4()),
                name=category_name,
            )
        )


def downgrade():
    op.drop_table('default_category_templates')