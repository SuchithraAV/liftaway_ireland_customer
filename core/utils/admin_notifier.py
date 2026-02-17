"""
Admin Backend Notifier - Event-driven payment communication
"""
import json
import logging
from typing import Optional
from uuid import UUID
from core.redis_client import get_redis

logger = logging.getLogger(__name__)

async def notify_payment_completed(
    job_id: UUID,
    total_amount: float,
    customer_id: UUID,
    driver_id: Optional[UUID] = None
):
    """
    Notify admin backend of completed payment via Redis pub/sub
    """
    try:
        redis_client = await get_redis()
        
        payment_data = {
            "event": "payment.completed",
            "job_id": str(job_id),
            "total_amount": total_amount,
            "customer_id": str(customer_id),
            "driver_id": str(driver_id) if driver_id else None,
            "timestamp": "2024-01-26T10:30:00Z"
        }
        
        # Publish to Redis channel
        await redis_client.publish("payment.events", json.dumps(payment_data))
        logger.info(f"Payment notification sent for job {job_id}")
        
    except Exception as e:
        logger.error(f"Failed to notify admin backend: {e}")
        # Don't raise - payment already completed successfully