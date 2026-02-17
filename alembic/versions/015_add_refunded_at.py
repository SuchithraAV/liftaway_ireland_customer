"""add_refunded_at_to_issues

Revision ID: 015_add_refunded_at
Revises: 014
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_add_refunded_at'
down_revision = 'b5e55d2eabc8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('issues', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('issues', 'refunded_at')
