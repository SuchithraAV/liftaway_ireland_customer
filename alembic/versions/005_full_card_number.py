"""Update to store full card number

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Change column name and increase size to 50
    op.alter_column('saved_payment_methods', 'card_last_twelve',
                   new_column_name='card_number',
                   existing_type=sa.String(length=12),
                   type_=sa.String(length=50))

def downgrade() -> None:
    # Change back to card_last_twelve with 12 length
    op.alter_column('saved_payment_methods', 'card_number',
                   new_column_name='card_last_twelve',
                   existing_type=sa.String(length=50),
                   type_=sa.String(length=12))