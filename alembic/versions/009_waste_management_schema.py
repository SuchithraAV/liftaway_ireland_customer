"""Waste Management Schema

Revision ID: 009_waste_management
Revises: 008_add_paid_at_to_issues
Create Date: 2024-01-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_waste_management'
down_revision = '008_add_paid_at_to_issues'
branch_labels = None
depends_on = None

def upgrade():
    # Pricing Slabs Table
    op.create_table('pricing_slabs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('load_type', sa.String(20), nullable=False),
        sa.Column('weight_min_kg', sa.Integer(), nullable=False),
        sa.Column('weight_max_kg', sa.Integer(), nullable=False),
        sa.Column('time_min_minutes', sa.Integer(), nullable=False),
        sa.Column('time_max_minutes', sa.Integer(), nullable=False),
        sa.Column('price_min_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('price_max_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('avg_price_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Waste Jobs Table (replaces issues for waste management)
    op.create_table('waste_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('load_type', sa.String(20), nullable=False),
        sa.Column('estimated_weight_kg', sa.Integer(), nullable=False),
        sa.Column('estimated_time_minutes', sa.Integer(), nullable=False),
        sa.Column('pickup_address', sa.Text(), nullable=False),
        sa.Column('pickup_postcode', sa.String(10), nullable=False),
        sa.Column('pickup_lat', sa.Float(), nullable=True),
        sa.Column('pickup_lng', sa.Float(), nullable=True),
        sa.Column('waste_description', sa.Text(), nullable=False),
        sa.Column('waste_images', sa.JSON(), nullable=True),
        sa.Column('customer_price_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('driver_price_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('platform_fee_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('ai_predicted_price', sa.DECIMAL(10, 2), nullable=True),
        sa.Column('specialist_waste_fee', sa.DECIMAL(10, 2), default=0),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('payment_status', sa.String(20), default='unpaid'),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('completion_otp', sa.String(6), nullable=True),
        sa.Column('scheduled_pickup_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'])
    )
    
    # Driver Earnings Table (enhanced)
    op.create_table('driver_daily_earnings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('jobs_completed', sa.Integer(), default=0),
        sa.Column('total_earnings_gbp', sa.DECIMAL(10, 2), default=0),
        sa.Column('total_customer_payments', sa.DECIMAL(10, 2), default=0),
        sa.Column('platform_fees_deducted', sa.DECIMAL(10, 2), default=0),
        sa.Column('payout_status', sa.String(20), default='pending'),
        sa.Column('stripe_payout_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id']),
        sa.UniqueConstraint('driver_id', 'date', name='unique_driver_daily_earnings')
    )
    
    # Platform Revenue Table
    op.create_table('platform_daily_revenue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_jobs', sa.Integer(), default=0),
        sa.Column('total_revenue_gbp', sa.DECIMAL(10, 2), default=0),
        sa.Column('total_customer_payments', sa.DECIMAL(10, 2), default=0),
        sa.Column('total_driver_payouts', sa.DECIMAL(10, 2), default=0),
        sa.Column('platform_fees_collected', sa.DECIMAL(10, 2), default=0),
        sa.Column('withdrawal_status', sa.String(20), default='available'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', name='unique_platform_daily_revenue')
    )
    
    # Job Transactions (audit trail)
    op.create_table('job_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transaction_type', sa.String(30), nullable=False),
        sa.Column('amount_gbp', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('stripe_reference', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['waste_jobs.id'])
    )

def downgrade():
    op.drop_table('job_transactions')
    op.drop_table('platform_daily_revenue')
    op.drop_table('driver_daily_earnings')
    op.drop_table('waste_jobs')
    op.drop_table('pricing_slabs')