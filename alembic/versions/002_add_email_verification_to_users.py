"""Add email verification columns to users table

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = 'b5e55d2eabc8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add email verification columns to users table if they don't exist
    try:
        op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), default=False))
    except Exception:
        # Column might already exist, ignore
        pass
    
    try:
        op.add_column('users', sa.Column('email_otp', sa.String(6), nullable=True))
    except Exception:
        # Column might already exist, ignore
        pass
    
    try:
        op.add_column('users', sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True))
    except Exception:
        # Column might already exist, ignore
        pass

def downgrade() -> None:
    # Remove email verification columns from users table
    try:
        op.drop_column('users', 'otp_expires_at')
    except Exception:
        pass
    
    try:
        op.drop_column('users', 'email_otp')
    except Exception:
        pass
    
    try:
        op.drop_column('users', 'is_email_verified')
    except Exception:
        pass