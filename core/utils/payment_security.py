"""
Payment Security & Error Handling Utilities
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
import stripe
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Circuit breaker state
circuit_state = {
    "failures": 0,
    "last_failure": None,
    "is_open": False
}
CIRCUIT_THRESHOLD = 5
CIRCUIT_TIMEOUT = 60

# Fraud detection
payment_attempts = {}
FRAUD_LIMIT = 5
FRAUD_WINDOW = 300


def circuit_breaker(func):
    """Circuit breaker for Stripe API calls"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if circuit is open
        if circuit_state["is_open"]:
            if datetime.utcnow().timestamp() - circuit_state["last_failure"] < CIRCUIT_TIMEOUT:
                logger.error("Circuit breaker OPEN - Stripe unavailable")
                raise HTTPException(status_code=503, detail="Payment service temporarily unavailable")
            else:
                circuit_state["is_open"] = False
                circuit_state["failures"] = 0
        
        try:
            result = await func(*args, **kwargs)
            circuit_state["failures"] = 0
            return result
        except Exception as e:
            circuit_state["failures"] += 1
            circuit_state["last_failure"] = datetime.utcnow().timestamp()
            
            if circuit_state["failures"] >= CIRCUIT_THRESHOLD:
                circuit_state["is_open"] = True
                logger.critical(f"Circuit breaker OPENED after {CIRCUIT_THRESHOLD} failures")
            
            raise
    
    return wrapper


async def create_payment_with_timeout(amount: int, metadata: Dict[str, Any], timeout: int = 10):
    """Create Stripe PaymentIntent with timeout"""
    try:
        payment_intent = await asyncio.wait_for(
            asyncio.to_thread(
                stripe.PaymentIntent.create,
                amount=amount,
                currency="gbp",
                metadata=metadata
            ),
            timeout=timeout
        )
        return payment_intent
    except asyncio.TimeoutError:
        logger.error(f"Stripe timeout for amount={amount}")
        raise HTTPException(status_code=504, detail="Payment service timeout")


async def retry_stripe_call(func, max_attempts: int = 3, *args, **kwargs):
    """Retry Stripe calls with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except stripe.error.RateLimitError:
            if attempt == max_attempts - 1:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Rate limited, retry {attempt + 1}/{max_attempts} in {wait_time}s")
            await asyncio.sleep(wait_time)
        except stripe.error.APIConnectionError:
            if attempt == max_attempts - 1:
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Connection error, retry {attempt + 1}/{max_attempts} in {wait_time}s")
            await asyncio.sleep(wait_time)


def validate_payment_amount(amount: float) -> int:
    """Validate and convert payment amount"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payment amount")
    
    if amount > 100000:
        raise HTTPException(status_code=400, detail="Amount exceeds £1000 maximum")
    
    if amount < 1:
        raise HTTPException(status_code=400, detail="Minimum payment is £1")
    
    return int(amount * 100)


async def check_fraud_pattern(customer_id: str, redis_client) -> bool:
    """Detect suspicious payment patterns"""
    key = f"fraud:attempts:{customer_id}"
    
    if redis_client:
        attempts = await redis_client.get(key)
        attempts = int(attempts) if attempts else 0
        
        if attempts >= FRAUD_LIMIT:
            logger.warning(f"Fraud detected: customer={customer_id}, attempts={attempts}")
            return True
        
        await redis_client.incr(key)
        await redis_client.expire(key, FRAUD_WINDOW)
    
    return False


async def is_webhook_processed(webhook_id: str, redis_client) -> bool:
    """Check if webhook already processed (idempotency)"""
    if not redis_client:
        return False
    
    key = f"webhook:processed:{webhook_id}"
    exists = await redis_client.exists(key)
    
    if exists:
        logger.info(f"Webhook {webhook_id} already processed")
        return True
    
    await redis_client.setex(key, 86400, "1")
    return False


async def compensate_failed_payment(payment_intent_id: str, issue_id: str):
    """Refund if DB update fails after charge"""
    try:
        refund = await asyncio.to_thread(
            stripe.Refund.create,
            payment_intent=payment_intent_id,
            reason="requested_by_customer"
        )
        logger.info(f"Compensation refund created: {refund.id} for issue {issue_id}")
        return refund
    except Exception as e:
        logger.critical(
            f"URGENT: Payment {payment_intent_id} charged but DB failed. "
            f"Refund also failed: {str(e)}. Manual intervention required!"
        )
        raise


def log_payment_event(event_type: str, data: Dict[str, Any]):
    """Audit trail for all payment events"""
    logger.info(f"PAYMENT_AUDIT: {event_type}", extra={
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        **data
    })
