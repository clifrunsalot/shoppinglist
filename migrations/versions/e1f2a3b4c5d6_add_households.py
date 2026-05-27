"""add households, household_members, household_invites; backfill household_id on items and stores

Revision ID: e1f2a3b4c5d6
Revises: c1d2e3f4a5b6
Create Date: 2026-05-26 00:00:00.000000

"""
import datetime

import sqlalchemy as sa
from alembic import op


revision = 'e1f2a3b4c5d6'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'households',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'household_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('household_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['household_id'], ['households.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('household_id', 'user_id', name='uq_household_member'),
    )

    op.create_table(
        'household_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('household_id', sa.Integer(), nullable=False),
        sa.Column('invited_email', sa.String(length=255), nullable=False),
        sa.Column('token', sa.String(length=100), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['household_id'], ['households.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )

    op.add_column('items', sa.Column('household_id', sa.Integer(), nullable=True))
    op.add_column('stores', sa.Column('household_id', sa.Integer(), nullable=True))

    # Data migration: create one household per user and backfill household_id.
    conn = op.get_bind()
    now = datetime.datetime.utcnow()

    users = conn.execute(sa.text('SELECT id FROM users')).fetchall()
    for user_row in users:
        user_id = user_row[0]

        conn.execute(
            sa.text('INSERT INTO households (created_at) VALUES (:ts)'),
            {'ts': now},
        )
        household_id = conn.execute(sa.text('SELECT MAX(id) FROM households')).scalar()

        conn.execute(
            sa.text(
                'INSERT INTO household_members '
                '(household_id, user_id, role, notifications_enabled, joined_at) '
                'VALUES (:hid, :uid, :role, :ne, :ts)'
            ),
            {'hid': household_id, 'uid': user_id, 'role': 'owner', 'ne': True, 'ts': now},
        )

        conn.execute(
            sa.text('UPDATE items SET household_id = :hid WHERE user_id = :uid'),
            {'hid': household_id, 'uid': user_id},
        )

        conn.execute(
            sa.text('UPDATE stores SET household_id = :hid WHERE user_id = :uid'),
            {'hid': household_id, 'uid': user_id},
        )


def downgrade():
    op.drop_column('stores', 'household_id')
    op.drop_column('items', 'household_id')
    op.drop_table('household_invites')
    op.drop_table('household_members')
    op.drop_table('households')
