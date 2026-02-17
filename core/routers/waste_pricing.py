"""
Waste Management Pricing API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

from core.database import get_db
from core.dependencies import get_current_customer
from core.pricing_engine import PricingEngine
from core.models import Customer

router = APIRouter(prefix="/waste/pricing", tags=["Waste Pricing"])

class PriceEstimateRequest(BaseModel):
    load_type: str  # minimum, quarter, half, three_quarter, full
    estimated_weight_kg: int
    estimated_time_minutes: int
    waste_description: str
    use_ai_prediction: bool = True

class PriceEstimateResponse(BaseModel):
    customer_price_gbp: float
    estimated_time_minutes: int
    load_type: str
    price_breakdown: dict
    ai_enhanced: bool
    
@router.post("/estimate", response_model=PriceEstimateResponse)
async def get_price_estimate(
    request: PriceEstimateRequest,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get price estimate for waste removal job
    Customer sees full price only - commission split is internal
    """
    try:
        pricing_result = await PricingEngine.calculate_price(
            load_type=request.load_type,
            estimated_weight_kg=request.estimated_weight_kg,
            estimated_time_minutes=request.estimated_time_minutes,
            waste_description=request.waste_description,
            db=db,
            use_ai=request.use_ai_prediction
        )
        
        return PriceEstimateResponse(
            customer_price_gbp=float(pricing_result["customer_price"]),
            estimated_time_minutes=request.estimated_time_minutes,
            load_type=request.load_type,
            price_breakdown={
                "base_price": float(pricing_result["customer_price"]),
                "specialist_waste_fee": 0.0,
                "total_price": float(pricing_result["customer_price"]),
                "currency": "GBP",
                "vat_excluded": True
            },
            ai_enhanced=pricing_result["ai_predicted_price"] is not None
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Price calculation failed")