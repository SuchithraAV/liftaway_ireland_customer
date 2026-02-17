"""
Customer Payment Flow - Handles FULL job amount only
No commission/split logic exposed to customer
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime
import stripe
import json
from typing import Optional
import logging

from core.database import get_db
from core.models import Issue, Customer
from core.dependencies import get_current_customer
from core.redis_client import get_redis
from core.utils.admin_notifier import notify_payment_completed
from core.utils.payment_security import (
    circuit_breaker,
    create_payment_with_timeout,
    retry_stripe_call,
    validate_payment_amount,
    check_fraud_pattern,
    compensate_failed_payment,
    log_payment_event
)
from config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Customer Payments"])


@router.post("/create-payment")
@circuit_breaker
async def create_payment(
    issue_id: UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Create Stripe PaymentIntent for FULL job amount
    Customer sees only total_cost - no split details
    """
    
    log_payment_event("payment_attempt", {
        "job_id": str(issue_id),
        "customer_id": str(customer.id)
    })
    
    # Fraud detection
    if await check_fraud_pattern(str(customer.id), redis_client):
        log_payment_event("fraud_blocked", {"customer_id": str(customer.id)})
        raise HTTPException(status_code=429, detail="Too many payment attempts. Try again later")
    
    # Idempotency check via Redis
    idempotency_key = f"payment:create:{issue_id}:{customer.id}"
    if redis_client:
        cached = await redis_client.get(idempotency_key)
        if cached:
            log_payment_event("idempotent_return", {"job_id": str(issue_id)})
            return json.loads(cached)
    
    # Fetch issue
    result = await db.execute(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()
    
    if not issue:
        log_payment_event("payment_failed", {"reason": "job_not_found", "job_id": str(issue_id)})
        raise HTTPException(status_code=404, detail="Job not found")
    
    if issue.status != "completed":
        log_payment_event("payment_failed", {"reason": "job_not_completed", "job_id": str(issue_id)})
        raise HTTPException(
            status_code=400, 
            detail="Payment only allowed after job completion. Current status: " + issue.status
        )
    
    if issue.payment_status == "paid":
        log_payment_event("payment_failed", {"reason": "already_paid", "job_id": str(issue_id)})
        raise HTTPException(status_code=400, detail="Job already paid")
    
    # Calculate final amount (negotiated or original)
    total_amount = issue.payment_amount
    if issue.negotiated_price and issue.negotiated_status == "accepted":
        total_amount = issue.negotiated_price
    
    # Validate amount
    amount_cents = validate_payment_amount(float(total_amount))
    
    payment_intent = None
    try:
        # Create PaymentIntent with timeout and retry
        payment_intent = await retry_stripe_call(
            create_payment_with_timeout,
            amount=amount_cents,
            metadata={
                "job_id": str(issue.id),
                "customer_id": str(customer.id)
            }
        )
        
        # Store payment reference
        try:
            issue.stripe_payment_intent_id = payment_intent.id
            await db.commit()
        except Exception as db_error:
            logger.error(f"DB commit failed: {str(db_error)}")
            # Note: PaymentIntent created but not charged yet - no refund needed
            # Customer can retry payment with same intent
            log_payment_event("payment_intent_db_failed", {
                "job_id": str(issue.id),
                "payment_id": payment_intent.id,
                "error": str(db_error)
            })
            raise HTTPException(status_code=500, detail="Payment processing failed. Please try again")
        
        response = {
            "payment_id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "job_id": str(issue.id),
            "total_amount": float(total_amount)
        }
        
        # Cache for 5 minutes
        if redis_client:
            await redis_client.setex(
                idempotency_key,
                300,
                json.dumps(response)
            )
        
        log_payment_event("payment_created", {
            "job_id": str(issue.id),
            "payment_id": payment_intent.id,
            "amount": float(total_amount)
        })
        
        return response
        
    except stripe.error.StripeError as e:
        log_payment_event("stripe_error", {
            "job_id": str(issue_id),
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-payment")
@circuit_breaker
async def verify_payment(
    payment_id: str,
    job_id: UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Verify payment status and update job
    Triggers internal split logic after confirmation
    """
    
    log_payment_event("verify_attempt", {
        "job_id": str(job_id),
        "payment_id": payment_id
    })
    
    # Fetch issue
    result = await db.execute(
        select(Issue).where(
            Issue.id == job_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if issue.stripe_payment_intent_id != payment_id:
        raise HTTPException(status_code=400, detail="Payment ID mismatch")
    
    try:
        # Verify with Stripe (with retry)
        payment_intent = await retry_stripe_call(
            lambda: stripe.PaymentIntent.retrieve(payment_id)
        )
        
        if payment_intent.status == "succeeded":
            # Atomic update to prevent race conditions
            result = await db.execute(
                update(Issue)
                .where(
                    Issue.id == job_id,
                    Issue.payment_status != "paid"
                )
                .values(
                    payment_status="paid",
                    paid_at=datetime.utcnow()
                )
                .returning(Issue.id)
            )
            await db.commit()
            
            updated = result.scalar_one_or_none()
            if not updated:
                log_payment_event("duplicate_verify", {"job_id": str(job_id)})
                return {"status": "already_processed"}
            
            # Cache payment status
            if redis_client:
                await redis_client.setex(
                    f"payment:status:{job_id}",
                    3600,
                    "paid"
                )
            
            # Trigger internal notification to admin backend
            await notify_payment_completed(
                job_id=job_id,
                total_amount=float(issue.payment_amount),
                customer_id=customer.id,
                driver_id=issue.assigned_driver_id
            )
            
            log_payment_event("payment_verified", {
                "job_id": str(job_id),
                "payment_id": payment_id,
                "amount": float(issue.payment_amount)
            })
            
            return {
                "status": "success",
                "payment_id": payment_id,
                "job_id": str(job_id),
                "total_amount": float(issue.payment_amount),
                "paid_at": issue.paid_at.isoformat()
            }
        else:
            return {
                "status": "pending",
                "payment_status": payment_intent.status
            }
            
    except stripe.error.StripeError as e:
        log_payment_event("verify_failed", {
            "job_id": str(job_id),
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/{job_id}")
async def get_payment_status(
    job_id: UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get payment status for a job
    Returns only customer-relevant information
    """
    
    # Check Redis cache first
    if redis_client:
        cached_status = await redis_client.get(f"payment:status:{job_id}")
        if cached_status:
            return {"job_id": str(job_id), "payment_status": cached_status}
    
    # Fetch from DB
    result = await db.execute(
        select(Issue).where(
            Issue.id == job_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": str(job_id),
        "payment_status": issue.payment_status,
        "total_amount": float(issue.payment_amount),
        "paid_at": issue.paid_at.isoformat() if issue.paid_at else None
    }
