"""Add saved payment methods table

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import core.models

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create saved_payment_methods table
    op.create_table('saved_payment_methods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', core.models.GUID(), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(length=255), nullable=False),
        sa.Column('card_last_four', sa.String(length=4), nullable=False),
        sa.Column('card_brand', sa.String(length=20), nullable=False),
        sa.Column('card_exp_month', sa.Integer(), nullable=False),
        sa.Column('card_exp_year', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    # Drop saved_payment_methods table
    op.drop_table('saved_payment_methods')