"""
LiftAway UK Pricing Engine with ChatGPT AI (2025 Benchmarks)
"""
from decimal import Decimal
from typing import Dict
import logging
from core.smart_pricing_algorithm import SmartPricingAlgorithm

logger = logging.getLogger(__name__)

class UKPricingEngine:
    """LiftAway UK-specific pricing with AI based on 2025 market benchmarks"""
    
    PLATFORM_COMMISSION = 20.0  # 20% platform fee (range: 20-30%)
    DRIVER_PAYOUT = 80.0  # 80% to driver (range: 70-80%)
    
    @staticmethod
    async def predict_uk_waste_price(
        category_id: int,
        description: str,
        quantity: int,
        urgency: str,
        vehicle_size: str,
        pickup_location: str
    ) -> Dict:
        """Smart algorithm-based pricing (No OpenAI)"""
        
        # Use Smart Pricing Algorithm
        pricing_result = SmartPricingAlgorithm.calculate_price(
            category_id=category_id,
            quantity=quantity,
            urgency=urgency,
            vehicle_size=vehicle_size,
            pickup_location=pickup_location,
            description=description
        )
        
        return {
            "estimated_price": pricing_result["estimated_price"],
            "ai_predicted_price": None,
            "currency": "GBP",
            "service_type": pricing_result["service_type"],
            "vehicle_size": vehicle_size,
            "urgency": urgency,
            "is_london": pricing_result["pricing_breakdown"]["location_multiplier"] > 1.0,
            "pricing_breakdown": pricing_result["pricing_breakdown"],
            "algorithm": "smart_rule_based"
        }