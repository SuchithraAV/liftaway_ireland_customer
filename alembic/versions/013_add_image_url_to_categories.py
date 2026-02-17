"""Add image_url to categories if missing

Revision ID: 013_add_image_url_to_categories
Revises: 012_remove_category_image_url
Create Date: 2025-01-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '013_add_image_url_to_categories'
down_revision = '012_remove_category_image_url'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('categories', 
        sa.Column('image_url', sa.String(5000), nullable=True)
    )
    
    # Set default values with professional waste management icons
    op.execute("""
        UPDATE categories 
        SET image_url = CASE 
            WHEN LOWER(name) LIKE '%household%' THEN 'https://cdn-icons-png.flaticon.com/512/2917/2917995.png'
            WHEN LOWER(name) LIKE '%recyclable%' THEN 'https://cdn-icons-png.flaticon.com/512/3524/3524388.png'
            WHEN LOWER(name) LIKE '%garden%' THEN 'https://cdn-icons-png.flaticon.com/512/628/628283.png'
            WHEN LOWER(name) LIKE '%c&d%' OR LOWER(name) LIKE '%construction%' THEN 'https://cdn-icons-png.flaticon.com/512/3004/3004458.png'
            WHEN LOWER(name) LIKE '%e-waste%' OR LOWER(name) LIKE '%ewaste%' THEN 'https://cdn-icons-png.flaticon.com/512/2913/2913133.png'
            WHEN LOWER(name) LIKE '%furniture%' THEN 'https://cdn-icons-png.flaticon.com/512/1670/1670828.png'
            WHEN LOWER(name) LIKE '%hazardous%' THEN 'https://cdn-icons-png.flaticon.com/512/3176/3176363.png'
            WHEN LOWER(name) LIKE '%metal%' THEN 'https://cdn-icons-png.flaticon.com/512/2917/2917242.png'
            WHEN LOWER(name) LIKE '%appliance%' THEN 'https://cdn-icons-png.flaticon.com/512/3004/3004458.png'
            WHEN LOWER(name) LIKE '%mixed%' THEN 'https://cdn-icons-png.flaticon.com/512/3524/3524636.png'
            ELSE 'https://cdn-icons-png.flaticon.com/512/3524/3524636.png'
        END
        WHERE image_url IS NULL
    """)
    
    # Make column non-nullable after setting defaults
    op.alter_column('categories', 'image_url', nullable=False)

def downgrade():
    op.drop_column('categories', 'image_url')
