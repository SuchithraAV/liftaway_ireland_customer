"""
In-Place Data Encryption Script

Encrypts existing PII data in the SAME columns (no schema changes needed).
This is a one-time migration to encrypt plaintext data.

⚠️ BACKUP YOUR DATABASE BEFORE RUNNING!

Usage:
    python encrypt_existing_data.py
"""

import asyncio
import sys
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.models import Customer, Driver, Admin, Issue, Company
from core.waste_models import WasteJob
from core.utils.field_encryption import (
    encrypt_phone, encrypt_email, encrypt_address, 
    encrypt_field, is_encrypted
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def encrypt_customers(db: AsyncSession):
    """Encrypt customer PII data in existing columns"""
    logger.info("Encrypting customers...")
    
    result = await db.execute(select(Customer))
    customers = result.scalars().all()
    
    count = 0
    for customer in customers:
        try:
            updates = {}
            
            if customer.phone_number and not is_encrypted(customer.phone_number):
                updates['phone_number'] = encrypt_phone(customer.phone_number)
            
            if customer.address and not is_encrypted(customer.address):
                updates['address'] = encrypt_address(customer.address)
            
            if customer.email and not is_encrypted(customer.email):
                updates['email'] = encrypt_email(customer.email)
            
            if customer.full_name and not is_encrypted(customer.full_name):
                updates['full_name'] = encrypt_field(customer.full_name)
            
            if updates:
                await db.execute(
                    update(Customer).where(Customer.id == customer.id).values(**updates)
                )
                count += 1
        
        except Exception as e:
            logger.error(f"Failed to encrypt customer {customer.id}: {e}")
    
    await db.commit()
    logger.info(f"✅ Encrypted {count} customers")


async def encrypt_drivers(db: AsyncSession):
    """Encrypt driver PII data in existing columns"""
    logger.info("Encrypting drivers...")
    
    result = await db.execute(select(Driver))
    drivers = result.scalars().all()
    
    count = 0
    for driver in drivers:
        try:
            updates = {}
            
            if driver.phone_number and not is_encrypted(driver.phone_number):
                updates['phone_number'] = encrypt_phone(driver.phone_number)
            
            if driver.email and not is_encrypted(driver.email):
                updates['email'] = encrypt_email(driver.email)
            
            if driver.full_name and not is_encrypted(driver.full_name):
                updates['full_name'] = encrypt_field(driver.full_name)
            
            if updates:
                await db.execute(
                    update(Driver).where(Driver.id == driver.id).values(**updates)
                )
                count += 1
        
        except Exception as e:
            logger.error(f"Failed to encrypt driver {driver.id}: {e}")
    
    await db.commit()
    logger.info(f"✅ Encrypted {count} drivers")


async def encrypt_admins(db: AsyncSession):
    """Encrypt admin PII data in existing columns"""
    logger.info("Encrypting admins...")
    
    result = await db.execute(select(Admin))
    admins = result.scalars().all()
    
    count = 0
    for admin in admins:
        try:
            if admin.phone_number and not is_encrypted(admin.phone_number):
                await db.execute(
                    update(Admin)
                    .where(Admin.id == admin.id)
                    .values(phone_number=encrypt_phone(admin.phone_number))
                )
                count += 1
        
        except Exception as e:
            logger.error(f"Failed to encrypt admin {admin.id}: {e}")
    
    await db.commit()
    logger.info(f"✅ Encrypted {count} admins")


async def encrypt_issues(db: AsyncSession):
    """Encrypt issue data in existing columns"""
    logger.info("Encrypting issues...")
    
    result = await db.execute(select(Issue))
    issues = result.scalars().all()
    
    count = 0
    for issue in issues:
        try:
            updates = {}
            
            if issue.pickup_location and not is_encrypted(issue.pickup_location):
                updates['pickup_location'] = encrypt_address(issue.pickup_location)
            
            if issue.description and not is_encrypted(issue.description):
                updates['description'] = encrypt_field(issue.description)
            
            if updates:
                await db.execute(
                    update(Issue).where(Issue.id == issue.id).values(**updates)
                )
                count += 1
        
        except Exception as e:
            logger.error(f"Failed to encrypt issue {issue.id}: {e}")
    
    await db.commit()
    logger.info(f"✅ Encrypted {count} issues")


async def encrypt_waste_jobs(db: AsyncSession):
    """Encrypt waste job data in existing columns"""
    logger.info("Encrypting waste jobs...")
    
    try:
        result = await db.execute(select(WasteJob))
        jobs = result.scalars().all()
        
        count = 0
        for job in jobs:
            try:
                updates = {}
                
                if job.pickup_address and not is_encrypted(job.pickup_address):
                    updates['pickup_address'] = encrypt_address(job.pickup_address)
                
                if job.pickup_postcode and not is_encrypted(job.pickup_postcode):
                    updates['pickup_postcode'] = encrypt_field(job.pickup_postcode)
                
                if job.waste_description and not is_encrypted(job.waste_description):
                    updates['waste_description'] = encrypt_field(job.waste_description)
                
                if updates:
                    await db.execute(
                        update(WasteJob).where(WasteJob.id == job.id).values(**updates)
                    )
                    count += 1
            
            except Exception as e:
                logger.error(f"Failed to encrypt waste job {job.id}: {e}")
        
        await db.commit()
        logger.info(f"✅ Encrypted {count} waste jobs")
    
    except Exception as e:
        logger.info(f"⚠️  Skipping waste_jobs table (doesn't exist): {e}")
        await db.rollback()


async def encrypt_companies(db: AsyncSession):
    """Encrypt company data in existing columns"""
    logger.info("Encrypting companies...")
    
    result = await db.execute(select(Company))
    companies = result.scalars().all()
    
    count = 0
    for company in companies:
        try:
            if company.address and not is_encrypted(company.address):
                await db.execute(
                    update(Company)
                    .where(Company.id == company.id)
                    .values(address=encrypt_address(company.address))
                )
                count += 1
        
        except Exception as e:
            logger.error(f"Failed to encrypt company {company.id}: {e}")
    
    await db.commit()
    logger.info(f"✅ Encrypted {count} companies")


async def main():
    """Run all encryption migrations"""
    logger.info("=" * 60)
    logger.info("🔒 Starting In-Place Data Encryption")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        try:
            await encrypt_customers(db)
            await encrypt_drivers(db)
            await encrypt_admins(db)
            await encrypt_issues(db)
            await encrypt_waste_jobs(db)
            await encrypt_companies(db)
            
            logger.info("=" * 60)
            logger.info("✅ Data encryption completed successfully!")
            logger.info("=" * 60)
            logger.info("📝 Next steps:")
            logger.info("1. Update application code to decrypt when reading")
            logger.info("2. Update application code to encrypt when writing")
            logger.info("3. Test thoroughly before deploying")
        
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await db.rollback()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
