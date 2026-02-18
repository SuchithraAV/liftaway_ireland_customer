from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, update
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.models import Issue, Category, Customer, DriverEarning, IssueStatus
from core.models import Notification
from core.schemas import IssueCreate, IssueResponse, IssueStatusUpdate, DriverEarningsResponse, IssueOTPResponse, NegotiateRequest, IssueDraftResponse, IssueDraftDataResponse
from core.dependencies import get_current_customer
from core.notifications_websocket import notifications_manager
from core.utils.cache import get_cached, set_cached, delete_cached
from core.utils.s3_upload import upload_file_to_s3, get_full_url
from core.utils.field_encryption import decrypt_field, decrypt_phone
from typing import List, Optional
from uuid import UUID
import random
import json
import stripe
from datetime import datetime, date
from decimal import Decimal
from config import settings
import uuid as uuid_lib
import asyncio

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer", tags=["Customer Issues"])

# Ensure stripe API key is configured
stripe.api_key = settings.STRIPE_SECRET_KEY

async def process_scheduled_issues(db: AsyncSession):
    """
    Check for scheduled issues that have reached their date and update them to pending.
    This should be called before querying issues to ensure data is up-to-date.
    """
    try:
        today = date.today()
        # Update scheduled issues where scheduled_date <= today to pending
        await db.execute(
            update(Issue)
            .where(
                Issue._status == "scheduled",
                Issue.scheduled_date <= today
            )
            .values(_status="pending")
        )
        await db.commit()
    except Exception as e:
        # Log error but don't stop the request
        print(f"Error processing scheduled issues: {str(e)}")
        await db.rollback()

@router.post("/issue", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def create_issue(
    category_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    pickup_location: Optional[str] = Form(None),
    postcode: Optional[str] = Form(None),
    quantity: Optional[int] = Form(None),
    urgency: Optional[str] = Form(None),
    vehicle_size: Optional[str] = Form(None),
    access_difficulty: Optional[str] = Form(None),
    scheduled_date: Optional[str] = Form(None),
    volume_load: Optional[str] = Form(None),
    images: UploadFile = File(default=None),
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Create a new waste pickup issue - Images are OPTIONAL"""
    
    # Validate required fields
    if not category_id:
        raise HTTPException(status_code=400, detail="category_id is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")
    if not pickup_location:
        raise HTTPException(status_code=400, detail="pickup_location is required")
    
    try:
        # Verify category exists
        category_result = await db.execute(select(Category).where(Category.id == category_id))
        category = category_result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Upload images to Utho Object Storage (OPTIONAL)
        image_urls = []
        if images and images.filename:
            try:
                object_key = await upload_file_to_s3(images, str(current_customer.id), f"issue_image_{random.randint(1000, 9999)}")
                if object_key:
                    image_urls.append(get_full_url(object_key))
                    logger.info(f"Image uploaded: {object_key}")
            except Exception as img_error:
                logger.warning(f"Image upload failed (non-fatal): {img_error}")
        
        # Map volume_load to quantity if provided
        if volume_load and not quantity:
            volume_map = {
                "small_bag": 1,
                "medium_load": 3,
                "large_load": 6,
                "van_load": 10,
                "truck_load": 15
            }
            quantity = volume_map.get(volume_load.lower(), 3)
        
        # Normalize urgency values
        urgency_map = {
            "standard": "normal",
            "emergency": "urgent",
            "immediate": "urgent",
            "same-day": "same_day",
            "tomorrow": "normal"
        }
        if urgency:
            urgency = urgency_map.get(urgency.lower(), urgency.lower())
        
        # Normalize vehicle size
        vehicle_map = {
            "auto": "small_van",
            "van": "large_van"
        }
        if vehicle_size:
            vehicle_size = vehicle_map.get(vehicle_size.lower(), vehicle_size.lower())
        
        # Build enhanced description
        enhanced_description = description or ""
        if access_difficulty:
            enhanced_description += f" Access: {access_difficulty}."
        if volume_load:
            enhanced_description += f" Volume: {volume_load}."
        if postcode:
            enhanced_description += f" Postcode: {postcode}."
        
        # AI Price Prediction (OPTIONAL - with fallback)
        ai_predicted_price = None
        final_amount = 50.0  # Default UK waste collection price
        
        if quantity and urgency and vehicle_size:
            try:
                from core.uk_pricing_engine import UKPricingEngine
                pricing_result = await UKPricingEngine.predict_uk_waste_price(
                    category_id=category_id,
                    description=enhanced_description,
                    quantity=quantity,
                    urgency=urgency,
                    vehicle_size=vehicle_size,
                    pickup_location=pickup_location or ""
                )
                ai_predicted_price = pricing_result.get("ai_predicted_price")
                final_amount = float(pricing_result["estimated_price"])
                logger.info(f"Pricing calculated: £{final_amount}")
            except Exception as pricing_error:
                logger.warning(f"Pricing failed (using default £50): {pricing_error}")
                final_amount = 50.0
        else:
            logger.info("Pricing parameters missing, using default: £50")
        
        # Generate 6-digit OTP
        otp_code = f"{random.randint(100000, 999999)}"
        
        # Handle scheduling logic
        status_val = "awaiting_payment"  # All new issues require payment first
        scheduled_date_val = None
        
        if scheduled_date:
            try:
                scheduled_date_obj = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
                today = date.today()
                if scheduled_date_obj < today:
                    raise HTTPException(status_code=400, detail="Scheduled date must be in the future")
                # Keep awaiting_payment status even for scheduled issues
                scheduled_date_val = scheduled_date_obj
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Create issue
        new_issue = Issue(
            customer_id=current_customer.id,
            category_id=category_id,
            description=enhanced_description,
            pickup_location=pickup_location,
            images=image_urls if image_urls else [],  # Always store as list
            otp_code=otp_code,
            payment_amount=Decimal(str(final_amount)),
            status=status_val,
            scheduled_date=scheduled_date_val
        )
        
        # Store waste management data
        waste_data = {
            "quantity": quantity,
            "urgency": urgency,
            "vehicle_size": vehicle_size,
            "access_difficulty": access_difficulty,
            "volume_load": volume_load,
            "postcode": postcode,
            "ai_predicted_price": float(ai_predicted_price) if ai_predicted_price else None
        }
        new_issue.description = f"{enhanced_description}\n\nWaste Details: {json.dumps(waste_data)}"
        
        db.add(new_issue)
        await db.commit()
        await db.refresh(new_issue)
        
        logger.info(f"Issue created: {new_issue.id}")
        await delete_cached(f"customer_issues:{current_customer.id}")

        # Create notification (best-effort)
        try:
            note = Notification(
                user_id=current_customer.id,
                user_type='customer',
                title='Issue created',
                message=f'Your issue has been created and is pending assignment. Issue ID: {new_issue.id}',
                data={"issue_id": str(new_issue.id)},
                is_read=False
            )
            db.add(note)
            await db.commit()
            await db.refresh(note)
            try:
                await notifications_manager.send_notification(
                    "customer",
                    str(current_customer.id),
                    {
                        "id": str(note.id),
                        "title": note.title,
                        "message": note.message,
                        "data": note.data,
                        "is_read": note.is_read,
                        "created_at": note.created_at.isoformat() if note.created_at else None,
                    }
                )
            except Exception as ws_error:
                logger.warning(f"WebSocket notification failed: {ws_error}")
        except Exception as notif_error:
            logger.warning(f"Notification creation failed: {notif_error}")
            await db.rollback()
        
        # Prepare response
        driver_lat, driver_lng = None, None
        if getattr(new_issue, "driver_location", None):
            try:
                lat_str, lng_str = new_issue.driver_location.split(",")
                driver_lat = float(lat_str)
                driver_lng = float(lng_str)
            except Exception:
                driver_lat, driver_lng = None, None

        response_data = {
            "id": new_issue.id,
            "customer_id": new_issue.customer_id,
            "category_id": new_issue.category_id,
            "category_name": category.name,
            "description": new_issue.description,
            "pickup_location": new_issue.pickup_location,
            "images": new_issue.images if new_issue.images else [],
            "assigned_driver_id": new_issue.assigned_driver_id,
            "assigned_driver_name": None,
            "assigned_driver_phone": None,
            "driver_lat": driver_lat,
            "driver_lng": driver_lng,
            "status": new_issue.status,
            "otp_code": None,
            "payment_amount": new_issue.payment_amount,
            "negotiated_price": new_issue.negotiated_price,
            "negotiated_status": new_issue.negotiated_status,
            "payment_status": new_issue.payment_status,
            "scheduled_date": new_issue.scheduled_date,
            "created_at": new_issue.created_at,
            "updated_at": new_issue.updated_at
        }
        
        return IssueResponse(**response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions with original status codes
        raise
    except Exception as e:
        # Only unexpected exceptions become 500 errors
        await db.rollback()
        logger.error(f"Unexpected error creating issue: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create issue: {str(e)}")

@router.get("/issue", response_model=List[IssueResponse])
async def get_customer_issues(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get all issues for current customer - Cached with Redis invalidation on driver accept"""
    cache_key = f"customer_issues:{current_customer.id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    await process_scheduled_issues(db)
    try:
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.category), selectinload(Issue.assigned_driver))
            .where(Issue.customer_id == current_customer.id)
            .order_by(desc(Issue.created_at))
        )
        issues = result.scalars().all()
        
        response_issues = []
        for issue in issues:
            # Get driver location if assigned (stored as "lat,lng")
            driver_lat, driver_lng = None, None
            if getattr(issue, "driver_location", None):
                try:
                    lat_str, lng_str = issue.driver_location.split(",")
                    driver_lat = float(lat_str)
                    driver_lng = float(lng_str)
                except Exception:
                    driver_lat, driver_lng = None, None
            
            response_data = {
                "id": issue.id,
                "customer_id": issue.customer_id,
                "category_id": issue.category_id,
                "category_name": issue.category.name if issue.category else None,
                "description": issue.description,
                "pickup_location": issue.pickup_location,
                "images": issue.images,
                "assigned_driver_id": issue.assigned_driver_id,
                "assigned_driver_name": decrypt_field(issue.assigned_driver.full_name) if issue.assigned_driver else None,
                "assigned_driver_phone": decrypt_phone(issue.assigned_driver.phone_number) if issue.assigned_driver else None,
                "driver_lat": driver_lat,
                "driver_lng": driver_lng,
                "status": issue.status,
                "otp_code": None,
                "payment_amount": issue.payment_amount,
                "negotiated_price": issue.negotiated_price,
                "negotiated_status": issue.negotiated_status,
                "payment_status": issue.payment_status,
                "scheduled_date": issue.scheduled_date,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at
            }
            response_issues.append(IssueResponse(**response_data))
        
        await set_cached(cache_key, [r.model_dump() for r in response_issues], ttl=60)
        return response_issues
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issues: {str(e)}")


@router.post("/issue/{issue_id}/cancel", response_model=dict)
async def cancel_issue(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Cancel issue and process refund based on status
    
    Refund Policy:
    - awaiting_payment: Full refund (100%) - No payment made yet
    - pending/scheduled (no driver assigned): Full refund (100%)
    - assigned (driver accepted): Partial refund (50%) - Driver gets 50% cancellation fee
    - in_progress: No refund (0%) - Work already started
    - completed: Cannot cancel
    """
    try:
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.assigned_driver))
            .where(and_(Issue.id == issue_id, Issue.customer_id == current_customer.id))
        )
        issue = result.scalar_one_or_none()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Check if issue can be cancelled
        if issue.status == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel completed issue")
        
        if issue.status == "in_progress":
            raise HTTPException(status_code=400, detail="Cannot cancel issue that is in progress. Work has already started.")
        
        # Determine refund amount based on status
        refund_amount = 0
        refund_percentage = 0
        cancellation_fee = 0
        
        if issue.payment_status == "paid":
            # Use negotiated price if accepted, otherwise use payment_amount
            total_paid = float(issue.negotiated_price) if (issue.negotiated_status == "approved" and issue.negotiated_price) else float(issue.payment_amount)
            
            if issue.status in ["pending", "scheduled"] and issue.assigned_driver_id is None:
                # No driver assigned yet - Full refund
                refund_amount = total_paid
                refund_percentage = 100
            elif issue.status == "assigned":
                # Driver assigned but work not started - 50% refund, 50% to driver as cancellation fee
                refund_amount = total_paid * 0.50
                cancellation_fee = total_paid * 0.50
                refund_percentage = 50
            
            # Process Stripe refund if refund_amount > 0
            if refund_amount > 0 and issue.stripe_payment_intent_id:
                try:
                    refund = stripe.Refund.create(
                        payment_intent=issue.stripe_payment_intent_id,
                        amount=int(refund_amount * 100),  # Convert to cents
                        reason="requested_by_customer",
                        metadata={
                            "issue_id": str(issue.id),
                            "customer_id": str(current_customer.id),
                            "refund_percentage": refund_percentage
                        }
                    )
                    logger.info(f"Refund processed: {refund.id} - £{refund_amount}")
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe refund failed: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Refund processing failed: {str(e)}")
            
            # If driver gets cancellation fee, create earning record
            if cancellation_fee > 0 and issue.assigned_driver_id:
                from decimal import Decimal
                cancellation_earning = DriverEarning(
                    driver_id=issue.assigned_driver_id,
                    issue_id=issue.id,
                    date=datetime.now(),
                    jobs_done=0,  # Not a completed job
                    amount=Decimal(str(cancellation_fee)),
                    total_job_amount=Decimal(str(total_paid)),
                    platform_fee=Decimal("0.00"),  # No platform fee on cancellation
                    payout_status="pending"
                )
                db.add(cancellation_earning)
                logger.info(f"Cancellation fee £{cancellation_fee} assigned to driver {issue.assigned_driver_id}")
        
        # Update issue status
        issue.status = "cancelled"
        issue.payment_status = "refunded" if refund_amount > 0 else issue.payment_status
        issue.refunded_at = datetime.utcnow() if refund_amount > 0 else None
        
        await db.commit()
        
        # Clear cache
        await delete_cached(f"customer_issues:{current_customer.id}")
        
        # Send notifications
        try:
            # Customer notification
            cust_note = Notification(
                user_id=current_customer.id,
                user_type='customer',
                title='Issue Cancelled',
                message=f'Your issue has been cancelled. Refund: £{refund_amount:.2f} ({refund_percentage}%)',
                data={
                    "issue_id": str(issue.id),
                    "refund_amount": refund_amount,
                    "refund_percentage": refund_percentage
                }
            )
            db.add(cust_note)
            
            # Driver notification if assigned
            if issue.assigned_driver_id:
                driver_note = Notification(
                    user_id=issue.assigned_driver_id,
                    user_type='driver',
                    title='Job Cancelled',
                    message=f'Customer cancelled the job. Cancellation fee: £{cancellation_fee:.2f}',
                    data={
                        "issue_id": str(issue.id),
                        "cancellation_fee": cancellation_fee
                    }
                )
                db.add(driver_note)
            
            await db.commit()
            
            # Push WebSocket notifications
            try:
                await notifications_manager.send_notification(
                    "customer", str(current_customer.id),
                    {"id": str(cust_note.id), "title": cust_note.title, "message": cust_note.message, "data": cust_note.data, "is_read": False, "created_at": cust_note.created_at.isoformat() if cust_note.created_at else None}
                )
                if issue.assigned_driver_id:
                    await notifications_manager.send_notification(
                        "driver", str(issue.assigned_driver_id),
                        {"id": str(driver_note.id), "title": driver_note.title, "message": driver_note.message, "data": driver_note.data, "is_read": False, "created_at": driver_note.created_at.isoformat() if driver_note.created_at else None}
                    )
            except Exception:
                pass
        except Exception as notif_error:
            logger.warning(f"Notification failed: {notif_error}")
        
        return {
            "success": True,
            "message": "Issue cancelled successfully",
            "issue_id": str(issue_id),
            "refund_amount": refund_amount,
            "refund_percentage": refund_percentage,
            "cancellation_fee_to_driver": cancellation_fee,
            "refund_status": "processed" if refund_amount > 0 else "no_refund_needed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to cancel issue: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel issue: {str(e)}")

@router.post("/issue/{issue_id}/payment")
async def issue_payment(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe PaymentIntent for an issue and save the intent id on the Issue.
    If negotiated price is accepted, charge negotiated_price instead of payment_amount.
    """
    try:
        result = await db.execute(select(Issue).where(Issue.id == issue_id, Issue.customer_id == current_customer.id))
        issue = result.scalar_one_or_none()

        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        if issue.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Issue already paid")

        # Prefer negotiated price if it was accepted
        if getattr(issue, 'negotiated_status', None) == 'accepted' and getattr(issue, 'negotiated_price', None) is not None:
            amount_to_charge = issue.negotiated_price
        else:
            amount_to_charge = issue.payment_amount

        amount_cents = int(float(amount_to_charge) * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="gbp",
            metadata={
                "issue_id": str(issue.id),
                "customer_id": str(current_customer.id)
            }
        )

        issue.stripe_payment_intent_id = payment_intent.id
        await db.commit()

        return {"client_secret": payment_intent.client_secret, "payment_intent_id": payment_intent.id, "amount": amount_cents}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create payment intent: {str(e)}")

@router.get("/issue/{issue_id}", response_model=IssueResponse)
async def get_customer_issue(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get specific issue for current customer"""
    await process_scheduled_issues(db)
    try:
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.category), selectinload(Issue.assigned_driver))
            .where(and_(Issue.id == issue_id, Issue.customer_id == current_customer.id))
        )
        issue = result.scalar_one_or_none()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Get driver location if assigned (stored as "lat,lng")
        driver_lat, driver_lng = None, None
        if getattr(issue, "driver_location", None):
            try:
                lat_str, lng_str = issue.driver_location.split(",")
                driver_lat = float(lat_str)
                driver_lng = float(lng_str)
            except Exception:
                driver_lat, driver_lng = None, None
        
        response_data = {
            "id": issue.id,
            "customer_id": issue.customer_id,
            "category_id": issue.category_id,
            "category_name": issue.category.name if issue.category else None,
            "description": issue.description,
            "pickup_location": issue.pickup_location,
            "images": issue.images,
            "assigned_driver_id": issue.assigned_driver_id,
            "assigned_driver_name": decrypt_field(issue.assigned_driver.full_name) if issue.assigned_driver else None,
            "assigned_driver_phone": decrypt_phone(issue.assigned_driver.phone_number) if issue.assigned_driver else None,
            "driver_lat": driver_lat,
            "driver_lng": driver_lng,
            "status": issue.status,
            "otp_code": None,
            "payment_amount": issue.payment_amount,
            "negotiated_price": issue.negotiated_price,
            "negotiated_status": issue.negotiated_status,
            "payment_status": issue.payment_status,
            "scheduled_date": issue.scheduled_date,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at
        }
        
        return IssueResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issue: {str(e)}")

@router.get("/issue/{issue_id}/otp", response_model=IssueOTPResponse)
async def get_issue_otp(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get issue status - OTP is sent via SMS only"""
    try:
        result = await db.execute(
            select(Issue).where(and_(Issue.id == issue_id, Issue.customer_id == current_customer.id))
        )
        issue = result.scalar_one_or_none()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        if issue.status == "pending":
            raise HTTPException(status_code=400, detail="Issue not yet accepted by driver")
        
        return IssueOTPResponse(
            status=issue.status,
            otp_code="OTP sent via SMS"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issue status: {str(e)}")

@router.post("/estimate-price")
async def estimate_uk_waste_price(
    category_id: int = Form(...),
    description: str = Form(""),
    quantity: Optional[int] = Form(None),
    urgency: str = Form(...),
    vehicle_size: str = Form(...),
    pickup_location: str = Form(""),
    postcode: Optional[str] = Form(None),
    access_difficulty: Optional[str] = Form(None),
    volume_load: Optional[str] = Form(None),
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get AI-powered price estimation for UK waste collection - Supports all 3 flows"""
    try:
        # Map volume_load to quantity if provided
        if volume_load and not quantity:
            volume_map = {
                "small_bag": 1,
                "1-2_bags": 1,
                "medium_load": 3,
                "3-5_bags": 3,
                "large_load": 6,
                "6+_bags": 6,
                "van_load": 10,
                "truck_load": 15
            }
            quantity = volume_map.get(volume_load.lower().replace(" ", "_"), 3)
        
        # Normalize urgency values
        urgency_map = {
            "standard": "normal",
            "emergency": "urgent",
            "immediate": "urgent",
            "immediate_pickup": "urgent",
            "same-day": "same_day",
            "same_day": "same_day",
            "tomorrow": "normal",
            "schedule": "normal"
        }
        urgency_normalized = urgency_map.get(urgency.lower(), urgency.lower())
        
        # Normalize vehicle size
        vehicle_map = {
            "auto": "small_van",
            "van": "large_van"
        }
        vehicle_normalized = vehicle_map.get(vehicle_size.lower(), vehicle_size.lower())
        
        # Build enhanced description
        enhanced_description = description
        if access_difficulty:
            enhanced_description += f" Access: {access_difficulty}."
        if volume_load:
            enhanced_description += f" Volume: {volume_load}."
        if postcode:
            enhanced_description += f" Postcode: {postcode}."
        
        from core.uk_pricing_engine import UKPricingEngine
        pricing_result = await UKPricingEngine.predict_uk_waste_price(
            category_id=category_id,
            description=enhanced_description,
            quantity=quantity or 1,
            urgency=urgency_normalized,
            vehicle_size=vehicle_normalized,
            pickup_location=pickup_location
        )
        
        return {
            "estimated_price_gbp": float(pricing_result["estimated_price"]),
            "ai_predicted_price": float(pricing_result["ai_predicted_price"]) if pricing_result["ai_predicted_price"] else None,
            "service_type": pricing_result["service_type"],
            "vehicle_size": vehicle_normalized,
            "urgency": urgency_normalized,
            "quantity": quantity or 1,
            "volume_load": volume_load,
            "access_difficulty": access_difficulty,
            "postcode": postcode,
            "pricing_breakdown": pricing_result["pricing_breakdown"],
            "ai_enhanced": pricing_result["ai_predicted_price"] is not None,
            "currency": "GBP",
            "vat_excluded": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"UK price estimation failed: {str(e)}")

@router.post("/issue/{issue_id}/negotiate", response_model=IssueResponse)
async def negotiate_issue_price(
    issue_id: UUID,
    negotiate_data: NegotiateRequest,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Negotiate the price for an issue"""


    try:
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.category), selectinload(Issue.assigned_driver))
            .where(and_(Issue.id == issue_id, Issue.customer_id == current_customer.id))
        )
        issue = result.scalar_one_or_none()
        
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Check if issue is in a valid state for negotiation
        if issue.status == "completed":
            raise HTTPException(status_code=400, detail="Cannot negotiate a completed issue")
        
        if issue.payment_status == "paid":
            raise HTTPException(status_code=400, detail="Cannot negotiate an already paid issue")
        
        # Update negotiated price and status
        issue.negotiated_price = negotiate_data.amount
        issue.negotiated_status = "pending"
        
        await db.commit()
        await db.refresh(issue)
        
        # Get driver location if assigned
        driver_lat, driver_lng = None, None
        if getattr(issue, "driver_location", None):
            try:
                lat_str, lng_str = issue.driver_location.split(",")
                driver_lat = float(lat_str)
                driver_lng = float(lng_str)
            except Exception:
                driver_lat, driver_lng = None, None
        
        response_data = {
            "id": issue.id,
            "customer_id": issue.customer_id,
            "category_id": issue.category_id,
            "category_name": issue.category.name if issue.category else None,
            "description": issue.description,
            "pickup_location": issue.pickup_location,
            "images": issue.images,
            "assigned_driver_id": issue.assigned_driver_id,
            "assigned_driver_name": issue.assigned_driver.full_name if issue.assigned_driver else None,
            "assigned_driver_phone": issue.assigned_driver.phone_number if issue.assigned_driver else None,
            "driver_lat": driver_lat,
            "driver_lng": driver_lng,
            "status": issue.status,
            "otp_code": None,
            "payment_amount": issue.payment_amount,
            "negotiated_price": issue.negotiated_price,
            "negotiated_status": issue.negotiated_status,
            "payment_status": issue.payment_status,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at
        }
        
        return IssueResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to negotiate price: {str(e)}")

# ==================== DRAFT ISSUE APIs (React → Flutter Flow) ====================

# Rate limit helper for draft creation
async def check_draft_rate_limit(request: Request) -> str:
    """Rate limit: 500 drafts per IP per minute (REQUIRES Redis)"""
    from core.redis_client import redis_client
    
    client_ip = request.client.host
    
    if not redis_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Draft service temporarily unavailable. Please try again later."
        )
    
    redis = redis_client.get_client()
    key = f"draft_rate_limit:{client_ip}"
    count = await redis.incr(key)
    
    if count == 1:
        await redis.expire(key, 60)
    
    if count > 500:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many draft requests. Please wait a minute.",
            headers={"Retry-After": "60"}
        )
    
    return client_ip

@router.post("/issue/draft", response_model=IssueDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_issue_draft(
    request: Request,
    category_id: int = Form(...),
    description: str = Form(...),
    pickup_location: str = Form(...),
    quantity: Optional[int] = Form(None),
    urgency: Optional[str] = Form(None),
    vehicle_size: Optional[str] = Form(None),
    postcode: Optional[str] = Form(None),
    access_difficulty: Optional[str] = Form(None),
    volume_load: Optional[str] = Form(None),
    scheduled_date: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Create draft issue (NO AUTH, RATE LIMITED) - For React to get price before login"""
    try:
        from core.redis_client import redis_client
        from core.uk_pricing_engine import UKPricingEngine
        
        # Check Redis availability first
        logger.info(f"Draft endpoint called - Redis available: {redis_client.is_available()}")
        
        if not redis_client.is_available():
            logger.error("Draft endpoint: Redis is NOT available")
            raise HTTPException(
                status_code=503, 
                detail="Draft service temporarily unavailable. Redis is not connected."
            )
        
        logger.info("Draft endpoint: Redis check passed, proceeding with rate limit")
        
        # Rate limiting (500 drafts per IP per minute)
        await check_draft_rate_limit(request)
        
        redis = redis_client.get_client()
        logger.info(f"Draft endpoint: Got Redis client: {redis}")
        
        # Get cached category (avoid DB query)
        cache_key = f"category:{category_id}"
        cached_category = await get_cached(cache_key)
        
        if cached_category:
            category_name = cached_category.get("name")
        else:
            category_result = await db.execute(select(Category).where(Category.id == category_id))
            category = category_result.scalar_one_or_none()
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            category_name = category.name
            await set_cached(cache_key, {"id": category.id, "name": category.name}, ttl=3600)
        
        # Map volume_load to quantity
        if volume_load and not quantity:
            volume_map = {
                "small_bag": 1, "medium_load": 3, "large_load": 6,
                "van_load": 10, "truck_load": 15
            }
            quantity = volume_map.get(volume_load.lower(), 3)
        
        # Normalize urgency
        urgency_map = {
            "standard": "normal", "emergency": "urgent", "immediate": "urgent",
            "same-day": "same_day", "tomorrow": "normal"
        }
        urgency_normalized = urgency_map.get(urgency.lower(), urgency.lower()) if urgency else "normal"
        
        # Normalize vehicle size
        vehicle_map = {"auto": "small_van", "van": "large_van"}
        vehicle_normalized = vehicle_map.get(vehicle_size.lower(), vehicle_size.lower()) if vehicle_size else "small_van"
        
        # Build enhanced description
        enhanced_description = description
        if access_difficulty:
            enhanced_description += f" Access: {access_difficulty}."
        if volume_load:
            enhanced_description += f" Volume: {volume_load}."
        if postcode:
            enhanced_description += f" Postcode: {postcode}."
        
        # Calculate price with timeout (3 seconds max)
        final_amount = 50.0
        ai_predicted_price = None
        try:
            pricing_result = await asyncio.wait_for(
                UKPricingEngine.predict_uk_waste_price(
                    category_id=category_id,
                    description=enhanced_description,
                    quantity=quantity or 1,
                    urgency=urgency_normalized,
                    vehicle_size=vehicle_normalized,
                    pickup_location=pickup_location
                ),
                timeout=3.0
            )
            ai_predicted_price = pricing_result.get("ai_predicted_price")
            final_amount = float(pricing_result["estimated_price"])
        except asyncio.TimeoutError:
            logger.warning(f"Pricing timeout, using default £50")
        except Exception as pricing_error:
            logger.warning(f"Pricing failed, using default £50: {pricing_error}")
        
        # Generate draft_id
        draft_id = str(uuid_lib.uuid4())
        
        # Save to Redis
        draft_data = {
            "category_id": category_id,
            "category_name": category_name,
            "description": enhanced_description,
            "pickup_location": pickup_location,
            "quantity": quantity,
            "urgency": urgency_normalized,
            "vehicle_size": vehicle_normalized,
            "postcode": postcode,
            "access_difficulty": access_difficulty,
            "volume_load": volume_load,
            "scheduled_date": scheduled_date,
            "estimated_price": final_amount,
            "ai_predicted_price": float(ai_predicted_price) if ai_predicted_price else None,
            "created_at": datetime.utcnow().isoformat()
        }
        await redis.setex(f"draft:{draft_id}", 3600, json.dumps(draft_data))
        logger.info(f"Draft created: {draft_id} with price £{final_amount}")
        
        return IssueDraftResponse(
            draft_id=draft_id,
            estimated_price=final_amount,
            expires_in_seconds=3600
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create draft: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create draft: {str(e)}")

@router.get("/issue/draft/{draft_id}", response_model=IssueDraftDataResponse)
async def get_issue_draft(
    draft_id: str,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get draft issue data (AUTH REQUIRED) - For Flutter after login"""
    try:
        from core.redis_client import redis_client
        
        if not redis_client.is_available():
            raise HTTPException(status_code=503, detail="Redis unavailable")
        
        redis = redis_client.get_client()
        
        # Fetch from Redis
        draft_data_str = await redis.get(f"draft:{draft_id}")
        if not draft_data_str:
            raise HTTPException(status_code=404, detail="Draft not found or expired")
        
        draft_data = json.loads(draft_data_str)
        
        return IssueDraftDataResponse(
            draft_id=draft_id,
            **draft_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get draft: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get draft: {str(e)}")

@router.post("/issue/confirm/{draft_id}", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def confirm_issue_draft(
    draft_id: str,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Confirm draft and create real issue (AUTH REQUIRED, IDEMPOTENT) - For Flutter after user confirms"""
    try:
        from core.redis_client import redis_client
        
        if not redis_client.is_available():
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        
        redis = redis_client.get_client()
        
        # Idempotency check: Prevent duplicate bookings
        confirmed_key = f"confirmed:{draft_id}"
        if await redis.exists(confirmed_key):
            raise HTTPException(
                status_code=409, 
                detail="This booking has already been confirmed. Check your bookings list."
            )
        
        # Fetch from Redis
        draft_data_str = await redis.get(f"draft:{draft_id}")
        if not draft_data_str:
            raise HTTPException(status_code=404, detail="Draft not found or expired (30 min limit)")
        
        draft_data = json.loads(draft_data_str)
        
        # Verify category still exists (use cache)
        cache_key = f"category:{draft_data['category_id']}"
        cached_category = await get_cached(cache_key)
        
        if cached_category:
            category_name = cached_category.get("name")
        else:
            category_result = await db.execute(select(Category).where(Category.id == draft_data["category_id"]))
            category = category_result.scalar_one_or_none()
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            category_name = category.name
            await set_cached(cache_key, {"id": category.id, "name": category.name}, ttl=3600)
        
        # Generate OTP
        otp_code = f"{random.randint(100000, 999999)}"
        
        # Handle scheduling
        status_val = "awaiting_payment"  # All new issues require payment first
        scheduled_date_val = None
        if draft_data.get("scheduled_date"):
            try:
                scheduled_date_obj = datetime.strptime(draft_data["scheduled_date"], "%Y-%m-%d").date()
                today = date.today()
                if scheduled_date_obj > today:
                    scheduled_date_val = scheduled_date_obj
            except ValueError:
                pass
        
        # Create issue
        new_issue = Issue(
            customer_id=current_customer.id,
            category_id=draft_data["category_id"],
            description=draft_data["description"],
            pickup_location=draft_data["pickup_location"],
            images=[],
            otp_code=otp_code,
            payment_amount=Decimal(str(draft_data["estimated_price"])),
            status=status_val,
            scheduled_date=scheduled_date_val
        )
        
        db.add(new_issue)
        await db.commit()
        await db.refresh(new_issue)
        
        # Mark as confirmed (prevent duplicate submissions)
        await redis.setex(confirmed_key, 3600, "1")  # 1 hour
        
        # Delete draft from Redis
        await redis.delete(f"draft:{draft_id}")
        logger.info(f"Draft {draft_id} confirmed, issue created: {new_issue.id}")
        
        # Clear cache
        await delete_cached(f"customer_issues:{current_customer.id}")
        
        # Create notification (best-effort)
        try:
            note = Notification(
                user_id=current_customer.id,
                user_type='customer',
                title='Booking confirmed',
                message=f'Your booking has been created successfully. Issue ID: {new_issue.id}',
                data={"issue_id": str(new_issue.id)},
                is_read=False
            )
            db.add(note)
            await db.commit()
        except Exception as notif_error:
            logger.warning(f"Notification creation failed: {notif_error}")
        
        # Prepare response
        response_data = {
            "id": new_issue.id,
            "customer_id": new_issue.customer_id,
            "category_id": new_issue.category_id,
            "category_name": category_name,
            "description": new_issue.description,
            "pickup_location": new_issue.pickup_location,
            "images": new_issue.images,
            "assigned_driver_id": None,
            "assigned_driver_name": None,
            "assigned_driver_phone": None,
            "driver_lat": None,
            "driver_lng": None,
            "status": new_issue.status,
            "otp_code": None,
            "payment_amount": new_issue.payment_amount,
            "negotiated_price": None,
            "negotiated_status": "none",
            "payment_status": new_issue.payment_status,
            "scheduled_date": new_issue.scheduled_date,
            "created_at": new_issue.created_at,
            "updated_at": new_issue.updated_at
        }
        
        return IssueResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to confirm draft: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to confirm draft: {str(e)}")

# ==================== END DRAFT APIs ====================

# Driver endpoints removed
driver_router = APIRouter(prefix="/driver", tags=["Driver Issues"])

# Additional router for /issues prefix
issues_router = APIRouter(prefix="/issues", tags=["Issues"])

@issues_router.get("/my-issues", response_model=List[IssueResponse])
async def get_my_issues(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get all issues for current customer (alias endpoint)"""
    await process_scheduled_issues(db)
    try:
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.category), selectinload(Issue.assigned_driver))
            .where(Issue.customer_id == current_customer.id)
            .order_by(desc(Issue.created_at))
        )
        issues = result.scalars().all()
        
        response_issues = []
        for issue in issues:
            driver_lat, driver_lng = None, None
            if getattr(issue, "driver_location", None):
                try:
                    lat_str, lng_str = issue.driver_location.split(",")
                    driver_lat = float(lat_str)
                    driver_lng = float(lng_str)
                except Exception:
                    driver_lat, driver_lng = None, None

            response_data = {
                "id": issue.id,
                "customer_id": issue.customer_id,
                "category_id": issue.category_id,
                "category_name": issue.category.name if issue.category else None,
                "description": issue.description,
                "pickup_location": issue.pickup_location,
                "images": issue.images,
                "assigned_driver_id": issue.assigned_driver_id,
                "assigned_driver_name": decrypt_field(issue.assigned_driver.full_name) if issue.assigned_driver else None,
                "assigned_driver_phone": decrypt_phone(issue.assigned_driver.phone_number) if issue.assigned_driver else None,
                "driver_lat": driver_lat,
                "driver_lng": driver_lng,
                "status": issue.status,
                "otp_code": issue.otp_code if issue.status != "pending" else None,
                "payment_amount": issue.payment_amount,
                "negotiated_price": issue.negotiated_price,
                "negotiated_status": issue.negotiated_status,
                "payment_status": issue.payment_status,
                "scheduled_date": issue.scheduled_date,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at
            }
            response_issues.append(IssueResponse(**response_data))
        
        return response_issues
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issues: {str(e)}")