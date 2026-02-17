"""Add OTP columns to breakdown_requests table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add OTP-related columns to breakdown_requests table
    op.add_column('breakdown_requests', sa.Column('start_otp', sa.String(6), nullable=True))
    op.add_column('breakdown_requests', sa.Column('completion_otp', sa.String(6), nullable=True))
    op.add_column('breakdown_requests', sa.Column('otp_start_verified', sa.Boolean(), default=False))
    op.add_column('breakdown_requests', sa.Column('otp_completion_verified', sa.Boolean(), default=False))

def downgrade() -> None:
    # Remove OTP-related columns from breakdown_requests table
    op.drop_column('breakdown_requests', 'otp_completion_verified')
    op.drop_column('breakdown_requests', 'otp_start_verified')
    op.drop_column('breakdown_requests', 'completion_otp')
    op.drop_column('breakdown_requests', 'start_otp')