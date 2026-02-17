"""Add waste management columns to existing tables

Revision ID: 010_waste_management_columns
Revises: 009_waste_management_schema
Create Date: 2024-01-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '010_waste_management_columns'
down_revision = '009_waste_management_schema'
branch_labels = None
depends_on = None

def upgrade():
    # Add waste-specific columns to existing issues table
    op.add_column('issues', sa.Column('load_type', sa.String(20), nullable=True))
    op.add_column('issues', sa.Column('estimated_weight_kg', sa.Integer(), nullable=True))
    op.add_column('issues', sa.Column('estimated_time_minutes', sa.Integer(), nullable=True))
    op.add_column('issues', sa.Column('ai_predicted_price', sa.DECIMAL(10, 2), nullable=True))
    op.add_column('issues', sa.Column('specialist_waste_fee', sa.DECIMAL(10, 2), default=0))
    
    # Create pricing slabs table (only new table needed)
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

def downgrade():
    op.drop_table('pricing_slabs')
    op.drop_column('issues', 'specialist_waste_fee')
    op.drop_column('issues', 'ai_predicted_price')
    op.drop_column('issues', 'estimated_time_minutes')
    op.drop_column('issues', 'estimated_weight_kg')
    op.drop_column('issues', 'load_type')