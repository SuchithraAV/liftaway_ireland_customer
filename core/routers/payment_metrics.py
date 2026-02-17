"""
Payment Monitoring & Metrics
Simple metrics endpoint for production monitoring
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from core.database import get_db
from core.models import Issue
from core.dependencies import get_current_customer

router = APIRouter(prefix="/payments/metrics", tags=["Payment Metrics"])


@router.get("/health")
async def payment_health_check(db: AsyncSession = Depends(get_db)):
    """
    Quick health check for payment system
    Returns payment statistics for monitoring
    """
    try:
        # Last 24 hours stats
        since = datetime.utcnow() - timedelta(hours=24)
        
        # Total payments in last 24h
        result = await db.execute(
            select(func.count(Issue.id))
            .where(
                Issue.payment_status == "paid",
                Issue.paid_at >= since
            )
        )
        payments_24h = result.scalar() or 0
        
        # Pending payments
        result = await db.execute(
            select(func.count(Issue.id))
            .where(Issue.payment_status == "pending")
        )
        pending = result.scalar() or 0
        
        # Failed/refunded
        result = await db.execute(
            select(func.count(Issue.id))
            .where(Issue.payment_status == "refunded")
        )
        refunded = result.scalar() or 0
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "payments_last_24h": payments_24h,
                "pending_payments": pending,
                "refunded_payments": refunded
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
