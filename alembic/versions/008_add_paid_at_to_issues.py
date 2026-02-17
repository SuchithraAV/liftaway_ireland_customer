"""add paid_at to issues

Revision ID: 008_add_paid_at
Revises: 007_remove_email_verification_columns
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_paid_at'
down_revision = '007_remove_email_verification_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('issues', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('issues', 'paid_at')
