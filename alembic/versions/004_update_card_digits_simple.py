"""Update card digits from 4 to 12 - simple version

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Simply change column name and size
    op.alter_column('saved_payment_methods', 'card_last_four',
                   new_column_name='card_last_twelve',
                   existing_type=sa.String(length=4),
                   type_=sa.String(length=12))

def downgrade() -> None:
    # Change back to original
    op.alter_column('saved_payment_methods', 'card_last_twelve',
                   new_column_name='card_last_four',
                   existing_type=sa.String(length=12),
                   type_=sa.String(length=4))