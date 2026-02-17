"""
Waste Job Management API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import secrets

from core.database import get_db
from core.dependencies import get_current_customer
from core.waste_models import WasteJob, JobTransaction
from core.pricing_engine import PricingEngine
from core.models import Customer

router = APIRouter(prefix="/waste/jobs", tags=["Waste Jobs"])

class CreateJobRequest(BaseModel):
    load_type: str
    estimated_weight_kg: int
    estimated_time_minutes: int
    pickup_address: str
    pickup_postcode: str
    waste_description: str
    waste_images: Optional[List[str]] = []
    scheduled_pickup_date: Optional[datetime] = None

class JobResponse(BaseModel):
    id: str
    load_type: str
    estimated_weight_kg: int
    pickup_address: str
    customer_price_gbp: float
    status: str
    payment_status: str
    scheduled_pickup_date: Optional[datetime]
    created_at: datetime

@router.post("/create", response_model=JobResponse)
async def create_waste_job(
    request: CreateJobRequest,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """
    Create new waste collection job with automatic pricing
    """
    try:
        # Calculate pricing
        pricing = await PricingEngine.calculate_price(
            load_type=request.load_type,
            estimated_weight_kg=request.estimated_weight_kg,
            estimated_time_minutes=request.estimated_time_minutes,
            waste_description=request.waste_description,
            db=db
        )
        
        # Create job with immutable pricing
        job = WasteJob(
            customer_id=customer.id,
            load_type=request.load_type,
            estimated_weight_kg=request.estimated_weight_kg,
            estimated_time_minutes=request.estimated_time_minutes,
            pickup_address=request.pickup_address,
            pickup_postcode=request.pickup_postcode,
            waste_description=request.waste_description,
            waste_images=request.waste_images,
            customer_price_gbp=pricing["customer_price"],
            driver_price_gbp=pricing["driver_price"],
            platform_fee_gbp=pricing["platform_fee"],
            ai_predicted_price=pricing["ai_predicted_price"],
            completion_otp=secrets.token_hex(3).upper(),
            scheduled_pickup_date=request.scheduled_pickup_date
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Create audit transaction
        transaction = JobTransaction(
            job_id=job.id,
            transaction_type="job_created",
            amount_gbp=pricing["customer_price"],
            status="pending",
            metadata={
                "pricing_breakdown": pricing["price_breakdown"],
                "slab_id": pricing["pricing_slab_id"]
            }
        )
        db.add(transaction)
        await db.commit()
        
        return JobResponse(
            id=str(job.id),
            load_type=job.load_type,
            estimated_weight_kg=job.estimated_weight_kg,
            pickup_address=job.pickup_address,
            customer_price_gbp=float(job.customer_price_gbp),
            status=job.status,
            payment_status=job.payment_status,
            scheduled_pickup_date=job.scheduled_pickup_date,
            created_at=job.created_at
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job creation failed: {str(e)}")

@router.get("/my-jobs", response_model=List[JobResponse])
async def get_my_jobs(
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get all jobs for current customer"""
    result = await db.execute(
        select(WasteJob).where(WasteJob.customer_id == customer.id)
        .order_by(WasteJob.created_at.desc())
    )
    jobs = result.scalars().all()
    
    return [
        JobResponse(
            id=str(job.id),
            load_type=job.load_type,
            estimated_weight_kg=job.estimated_weight_kg,
            pickup_address=job.pickup_address,
            customer_price_gbp=float(job.customer_price_gbp),
            status=job.status,
            payment_status=job.payment_status,
            scheduled_pickup_date=job.scheduled_pickup_date,
            created_at=job.created_at
        )
        for job in jobs
    ]