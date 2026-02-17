"""remove email verification columns

Revision ID: 007_remove_email_verification
Revises: 006_remove_saved_cards
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_remove_email_verification'
down_revision = '006_remove_saved_cards'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('customers', 'is_email_verified')
    op.drop_column('customers', 'email_otp')


def downgrade():
    op.add_column('customers', sa.Column('email_otp', sa.String(6), nullable=True))
    op.add_column('customers', sa.Column('is_email_verified', sa.Boolean(), default=False))
