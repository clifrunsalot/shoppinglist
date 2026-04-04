"""add admin templates and settings

Revision ID: 3c6a0bb190a1
Revises: 9b63b8b7c7d4
Create Date: 2026-04-04 09:00:00.000000

"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c6a0bb190a1'
down_revision = '9b63b8b7c7d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_table(
        'default_store_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_default_store_template_name'),
        sa.UniqueConstraint('template_key')
    )
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('target_type', sa.String(length=80), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'default_item_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(length=36), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False, server_default='1'),
        sa.Column('unit', sa.String(length=30), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('store_template_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['store_template_id'], ['default_store_templates.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_key')
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('is_approved', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('theme_preference', sa.String(length=20), nullable=True))

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('template_store_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_stores_template_store_id_default_store_templates', 'default_store_templates', ['template_store_id'], ['id'])

    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('template_item_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_items_template_item_id_default_item_templates', 'default_item_templates', ['template_item_id'], ['id'])

    bind = op.get_bind()
    metadata = sa.MetaData()

    users = sa.Table('users', metadata, autoload_with=bind)
    stores = sa.Table('stores', metadata, autoload_with=bind)
    items = sa.Table('items', metadata, autoload_with=bind)
    app_settings = sa.Table('app_settings', metadata, autoload_with=bind)
    default_store_templates = sa.Table('default_store_templates', metadata, autoload_with=bind)
    default_item_templates = sa.Table('default_item_templates', metadata, autoload_with=bind)

    bind.execute(app_settings.insert().values(key='default_theme', value='meadow'))
    bind.execute(users.update().values(is_approved=True, is_active=True))

    first_user_id = bind.execute(sa.select(users.c.id).order_by(users.c.id.asc()).limit(1)).scalar()
    if first_user_id is not None:
        bind.execute(users.update().where(users.c.id == first_user_id).values(is_admin=True))

    store_map = {}
    null_owned_stores = bind.execute(
        sa.select(stores.c.id, stores.c.name).where(stores.c.user_id.is_(None)).order_by(stores.c.id.asc())
    ).fetchall()
    for index, store_row in enumerate(null_owned_stores, start=1):
        inserted_store_template_id = bind.execute(
            default_store_templates.insert()
            .values(
                template_key=str(uuid4()),
                name=store_row.name,
                sort_order=index * 10,
            )
            .returning(default_store_templates.c.id)
        ).scalar_one()
        store_map[store_row.id] = inserted_store_template_id
        bind.execute(
            stores.update()
            .where(stores.c.id == store_row.id)
            .values(sort_order=index * 10, template_store_id=inserted_store_template_id)
        )

    null_owned_items = bind.execute(
        sa.select(
            items.c.id,
            items.c.name,
            items.c.quantity,
            items.c.unit,
            items.c.category,
            items.c.store_id,
        )
        .where(items.c.user_id.is_(None))
        .order_by(items.c.id.asc())
    ).fetchall()
    for index, item_row in enumerate(null_owned_items, start=1):
        inserted_item_template_id = bind.execute(
            default_item_templates.insert()
            .values(
                template_key=str(uuid4()),
                name=item_row.name,
                quantity=item_row.quantity if item_row.quantity is not None else 1,
                unit=item_row.unit,
                category=item_row.category,
                sort_order=index * 10,
                store_template_id=store_map.get(item_row.store_id),
            )
            .returning(default_item_templates.c.id)
        ).scalar_one()
        bind.execute(
            items.update()
            .where(items.c.id == item_row.id)
            .values(sort_order=index * 10, template_item_id=inserted_item_template_id)
        )

    bind.execute(
        stores.update()
        .where(stores.c.user_id.is_not(None))
        .values(sort_order=sa.case((stores.c.sort_order == 0, stores.c.id * 10), else_=stores.c.sort_order))
    )
    bind.execute(
        items.update()
        .where(items.c.user_id.is_not(None))
        .values(sort_order=sa.case((items.c.sort_order == 0, items.c.id * 10), else_=items.c.sort_order))
    )


def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_items_template_item_id_default_item_templates', type_='foreignkey')
        batch_op.drop_column('template_item_id')
        batch_op.drop_column('sort_order')

    with op.batch_alter_table('stores', schema=None) as batch_op:
        batch_op.drop_constraint('fk_stores_template_store_id_default_store_templates', type_='foreignkey')
        batch_op.drop_column('template_store_id')
        batch_op.drop_column('sort_order')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('theme_preference')
        batch_op.drop_column('is_active')
        batch_op.drop_column('is_approved')
        batch_op.drop_column('is_admin')

    op.drop_table('default_item_templates')
    op.drop_table('audit_logs')
    op.drop_table('default_store_templates')
    op.drop_table('app_settings')