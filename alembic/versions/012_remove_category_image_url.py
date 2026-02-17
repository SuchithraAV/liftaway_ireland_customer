"""Remove image_url from categories

Revision ID: 012_remove_category_image_url
Revises: 011_liftaway_pricing_update
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012_remove_category_image_url'
down_revision = '011_liftaway_pricing_update'
branch_labels = None
depends_on = None

def upgrade():
    # Remove image_url column from categories table
    op.drop_column('categories', 'image_url')

def downgrade():
    # Add image_url column back if needed
    op.add_column('categories', 
        sa.Column('image_url', sa.String(500), nullable=True)
    )
