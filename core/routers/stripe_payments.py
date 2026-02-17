from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime, date
import stripe
import logging

from core.database import get_db
from core.models import Issue, Customer, Driver, DriverEarning
from core.dependencies import get_current_customer
from core.schemas import StripePaymentIntentCreate
from core.redis_client import get_redis
from core.utils.payment_security import (
    is_webhook_processed,
    log_payment_event,
    validate_payment_amount
)
from config import settings

# ------------------------------------------------------------------
# Stripe config
# ------------------------------------------------------------------
stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["Stripe Payments"])


# ------------------------------------------------------------------
# CREATE CHECKOUT SESSION (Stripe Button)
# ------------------------------------------------------------------
@router.post("/create-checkout-session")
async def create_checkout_session(
    payment_data: StripePaymentIntentCreate,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """
    Create Stripe Checkout Session for an Issue payment
    """

    result = await db.execute(
        select(Issue).where(
            Issue.id == payment_data.issue_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Issue already paid")

    # Decide final amount
    amount = issue.payment_amount
    if issue.negotiated_price and issue.negotiated_status in ["approved", "accepted"]:
        amount = issue.negotiated_price

    # Validate amount
    amount_cents = validate_payment_amount(float(amount))

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],  # UPI auto-enabled in India
            allow_promotion_codes=True,  # Enable coupon/promo codes
            line_items=[
                {
                    "price_data": {
                        "currency": "gbp",
                        "product_data": {
                            "name": f"Issue Payment ({issue.id})"
                        },
                        "unit_amount": amount_cents
                    },
                    "quantity": 1
                }
            ],
            metadata={
                "issue_id": str(issue.id),
                "customer_id": str(customer.id)
            },
            success_url=f"{settings.BACKEND_URL}/static/stripe/success.html?payment_success=true&issue_id={issue.id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.BACKEND_URL}/static/stripe/success.html?payment_canceled=true&issue_id={issue.id}"
        )

        # We do NOT save session ID to DB as requested
        # issue.stripe_checkout_session_id = session.id
        # await db.commit()
        
        log_payment_event("checkout_session_created", {
            "issue_id": str(issue.id),
            "session_id": session.id,
            "amount": float(amount)
        })

        return {
            "checkout_url": session.url
        }

    except stripe.error.StripeError as e:
        log_payment_event("checkout_session_failed", {
            "issue_id": str(payment_data.issue_id),
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------
# STRIPE WEBHOOK (SINGLE SOURCE OF TRUTH)
# ------------------------------------------------------------------
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    # Webhook idempotency check
    if await is_webhook_processed(event["id"], redis_client):
        return {"status": "already_processed"}

    # --------------------------------------------------------------
    # Payment completed
    # --------------------------------------------------------------
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        issue_id = session["metadata"].get("issue_id")

        if issue_id:
            # Atomic update to prevent race conditions
            # Change status from awaiting_payment to pending (or scheduled if scheduled_date is in future)
            result = await db.execute(
                select(Issue).where(Issue.id == UUID(issue_id))
            )
            issue = result.scalar_one_or_none()
            
            if issue and issue.payment_status != "paid":
                # Determine new status based on scheduled_date
                new_status = "pending"
                if issue.scheduled_date and issue.scheduled_date > date.today():
                    new_status = "scheduled"
                
                # Update payment status and issue status
                await db.execute(
                    update(Issue)
                    .where(
                        Issue.id == UUID(issue_id),
                        Issue.payment_status != "paid"
                    )
                    .values(
                        payment_status="paid",
                        paid_at=datetime.utcnow(),
                        _status=new_status  # Change from awaiting_payment to pending/scheduled
                    )
                )
                await db.commit()
                
                log_payment_event("webhook_payment_completed", {
                    "issue_id": issue_id,
                    "session_id": session["id"],
                    "new_status": new_status
                })
                
                # Transfer to driver if job completed
                if issue.assigned_driver_id and issue.status == "completed":
                    await transfer_to_driver(issue, db)
            else:
                log_payment_event("webhook_duplicate", {"issue_id": issue_id})
    
    # --------------------------------------------------------------
    # Refund handling
    # --------------------------------------------------------------
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        payment_intent_id = charge["payment_intent"]
        
        result = await db.execute(
            select(Issue).where(
                Issue.stripe_payment_intent_id == payment_intent_id
            )
        )
        issue = result.scalar_one_or_none()
        
        if issue:
            issue.payment_status = "refunded"
            issue.refunded_at = datetime.utcnow()
            await db.commit()
            
            log_payment_event("refund_processed", {
                "issue_id": str(issue.id),
                "payment_intent_id": payment_intent_id
            })

    return {"status": "ok"}



# ------------------------------------------------------------------
# MANUAL CHECK (For Localhost where webhooks fail)
# ------------------------------------------------------------------
@router.post("/verify-session")
async def verify_session(
    issue_id: UUID,
    session_id: str,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually check if the Checkout Session for this Issue is paid.
    Useful for localhost development where webhooks cannot reach the server.
    """
    # 1. Fetch Issue
    result = await db.execute(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.payment_status == "paid" and issue.status in ["pending", "scheduled"]:
        return {"status": "paid", "message": "Already paid and status updated"}

    # 2. Retrieve Status from Stripe using the passed session_id
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify session belongs to this issue
    if session.metadata.get("issue_id") != str(issue.id):
        raise HTTPException(status_code=400, detail="Session does not match issue")

    # 3. Update DB if paid
    if session.payment_status == "paid":
        # Determine new status based on scheduled_date
        new_status = "pending"
        if issue.scheduled_date and issue.scheduled_date > date.today():
            new_status = "scheduled"
        
        issue.payment_status = "paid"
        issue.paid_at = datetime.utcnow()
        issue.status = new_status  # Update status to pending/scheduled
        await db.commit()

        # Trigger driver transfer immediately if needed
        if issue.assigned_driver_id and issue.status == "completed":
             await transfer_to_driver(issue, db)
        
        return {"status": "paid", "message": "Payment verified via API", "new_status": new_status}
    else:
         return {"status": session.payment_status, "message": "Payment not completed yet"}


# ------------------------------------------------------------------
# FIX PAID ISSUES WITH WRONG STATUS (Admin/Debug endpoint)
# ------------------------------------------------------------------
@router.post("/fix-paid-issue-status/{issue_id}")
async def fix_paid_issue_status(
    issue_id: UUID,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """
    Fix issues that are paid but have wrong status.
    This happens when webhook fails or doesn't fire.
    """
    result = await db.execute(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.customer_id == customer.id
        )
    )
    issue = result.scalar_one_or_none()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Check if issue is paid
    if issue.payment_status != "paid":
        raise HTTPException(status_code=400, detail="Issue is not paid yet")
    
    # Determine correct status
    new_status = "pending"
    if issue.scheduled_date and issue.scheduled_date > date.today():
        new_status = "scheduled"
    
    # Update if status is wrong
    if issue.status != new_status:
        issue.status = new_status
        await db.commit()
        
        return {
            "success": True,
            "message": f"Status updated from {issue.status} to {new_status}",
            "issue_id": str(issue_id),
            "new_status": new_status
        }
    else:
        return {
            "success": True,
            "message": "Status is already correct",
            "current_status": issue.status
        }


# ------------------------------------------------------------------
# DRIVER PAYOUT (STRIPE CONNECT)
# ------------------------------------------------------------------
async def transfer_to_driver(issue: Issue, db: AsyncSession):
    """
    Transfer money to driver (90%) after platform fee (10%)
    """

    result = await db.execute(
        select(Driver).where(Driver.id == issue.assigned_driver_id)
    )
    driver = result.scalar_one_or_none()

    if not driver or not driver.stripe_account_id:
        return

    try:
        total_amount_cents = int(float(issue.payment_amount) * 100)
        platform_fee = int(total_amount_cents * 0.10)
        driver_amount = total_amount_cents - platform_fee

        transfer = stripe.Transfer.create(
            amount=driver_amount,
            currency="gbp",
            destination=driver.stripe_account_id,
            transfer_group=str(issue.id)
        )

        earning_result = await db.execute(
            select(DriverEarning).where(DriverEarning.issue_id == issue.id)
        )
        earning = earning_result.scalar_one_or_none()

        if earning:
            earning.stripe_transfer_id = transfer.id
            earning.payout_status = "completed"
            earning.paid_at = datetime.utcnow()
            await db.commit()

    except stripe.error.StripeError as e:
        print("Driver transfer failed:", str(e))
