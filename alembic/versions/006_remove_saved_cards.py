"""Remove saved payment methods table

Revision ID: 006
Revises: 005
Create Date: 2024-01-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Drop saved_payment_methods table
    op.drop_table('saved_payment_methods')

def downgrade() -> None:
    # Recreate saved_payment_methods table
    op.create_table('saved_payment_methods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.CHAR(36), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(length=255), nullable=False),
        sa.Column('card_number', sa.String(length=50), nullable=False),
        sa.Column('card_brand', sa.String(length=20), nullable=False),
        sa.Column('card_exp_month', sa.Integer(), nullable=False),
        sa.Column('card_exp_year', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )