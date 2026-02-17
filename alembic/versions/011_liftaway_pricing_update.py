"""Update pricing slabs for LiftAway 2025 benchmarks

Revision ID: 011_liftaway_pricing_update
Revises: 010_waste_management_columns
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa

revision = '011_liftaway_pricing_update'
down_revision = '010_waste_management_columns'
branch_labels = None
depends_on = None

def upgrade():
    # Modify load_type column to support longer names
    op.alter_column('pricing_slabs', 'load_type',
                    existing_type=sa.String(20),
                    type_=sa.String(50),
                    existing_nullable=False)
    
    # Clear old data and insert new LiftAway pricing
    op.execute("DELETE FROM pricing_slabs")
    
    # Insert LiftAway 2025 pricing data
    op.execute("""
        INSERT INTO pricing_slabs (load_type, weight_min_kg, weight_max_kg, time_min_minutes, time_max_minutes, price_min_gbp, price_max_gbp, avg_price_gbp, is_active)
        VALUES
        ('single_item', 10, 100, 15, 30, 70, 150, 110, true),
        ('multiple_items', 100, 300, 30, 60, 150, 300, 225, true),
        ('full_van_local', 300, 600, 60, 120, 120, 180, 150, true),
        ('full_property_move', 600, 2000, 120, 480, 300, 1500, 900, true),
        ('household_waste', 50, 200, 20, 45, 60, 100, 80, true),
        ('garden_waste', 30, 150, 15, 40, 50, 75, 62, true),
        ('mixed_waste', 100, 400, 30, 90, 80, 200, 140, true),
        ('one_off_clearance', 150, 500, 45, 120, 80, 150, 115, true)
    """)

def downgrade():
    # Revert load_type column
    op.alter_column('pricing_slabs', 'load_type',
                    existing_type=sa.String(50),
                    type_=sa.String(20),
                    existing_nullable=False)
    
    # Clear LiftAway data
    op.execute("DELETE FROM pricing_slabs")
