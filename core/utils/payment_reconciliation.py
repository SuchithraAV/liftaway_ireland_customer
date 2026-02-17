"""
Payment Reconciliation Background Job
Runs every 5 minutes to catch missed webhooks
"""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from core.models import Issue
from core.database import AsyncSessionLocal
from config import settings

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


async def reconcile_payments():
    """Check Stripe for payments not reflected in DB"""
    logger.info("Starting payment reconciliation")
    
    async with AsyncSessionLocal() as db:
        try:
            # Get payments from last 24 hours
            since = int((datetime.utcnow() - timedelta(hours=24)).timestamp())
            payments = await asyncio.to_thread(
                stripe.PaymentIntent.list,
                limit=100,
                created={'gte': since}
            )
            
            reconciled = 0
            for payment in payments.data:
                if payment.status == 'succeeded':
                    job_id = payment.metadata.get('job_id')
                    if job_id:
                        result = await db.execute(
                            select(Issue).where(Issue.id == job_id)
                        )
                        issue = result.scalar_one_or_none()
                        
                        if issue and issue.payment_status != 'paid':
                            logger.warning(f"Missed webhook detected for job {job_id}")
                            issue.payment_status = 'paid'
                            issue.paid_at = datetime.utcfromtimestamp(payment.created)
                            issue.stripe_payment_intent_id = payment.id
                            await db.commit()
                            reconciled += 1
            
            logger.info(f"Reconciliation complete: {reconciled} payments synced")
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {str(e)}")


async def run_reconciliation_loop():
    """Run reconciliation every 5 minutes"""
    while True:
        try:
            await reconcile_payments()
        except Exception as e:
            logger.error(f"Reconciliation loop error: {str(e)}")
        
        await asyncio.sleep(300)  # 5 minutes
