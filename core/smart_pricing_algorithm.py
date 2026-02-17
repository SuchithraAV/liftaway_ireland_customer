"""
Advanced Pricing Algorithm - No OpenAI Required
Uses weighted scoring and market benchmarks
"""
from decimal import Decimal
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class SmartPricingAlgorithm:
    """Advanced rule-based pricing with market intelligence"""
    
    # UK Market Benchmarks (2025)
    CATEGORY_PROFILES = {
        1: {"base": 95, "weight_factor": 0.8, "time_factor": 1.2, "name": "Single Item"},
        2: {"base": 62, "weight_factor": 0.5, "time_factor": 0.8, "name": "Garden Waste"},
        3: {"base": 180, "weight_factor": 1.3, "time_factor": 1.3, "name": "Multiple Items"},
        4: {"base": 95, "weight_factor": 1.0, "time_factor": 1.0, "name": "Furniture"},
        5: {"base": 125, "weight_factor": 1.4, "time_factor": 1.4, "name": "Full Van"},
        6: {"base": 75, "weight_factor": 0.6, "time_factor": 1.0, "name": "Household Waste"},
        7: {"base": 110, "weight_factor": 1.0, "time_factor": 1.1, "name": "Mixed Waste"},
        8: {"base": 105, "weight_factor": 1.0, "time_factor": 1.1, "name": "Clearance"},
        9: {"base": 500, "weight_factor": 2.3, "time_factor": 2.3, "name": "Property Move"},
        10: {"base": 130, "weight_factor": 1.1, "time_factor": 1.2, "name": "E-Waste"},
        # Extended IDs
        25: {"base": 75, "weight_factor": 0.6, "time_factor": 1.0, "name": "Household"},
        26: {"base": 65, "weight_factor": 0.5, "time_factor": 0.9, "name": "Recyclables"},
        27: {"base": 62, "weight_factor": 0.5, "time_factor": 0.8, "name": "Garden"},
        28: {"base": 130, "weight_factor": 1.4, "time_factor": 1.3, "name": "Construction"},
        29: {"base": 130, "weight_factor": 1.1, "time_factor": 1.2, "name": "E-Waste"},
        30: {"base": 95, "weight_factor": 1.0, "time_factor": 1.0, "name": "Furniture"},
        31: {"base": 125, "weight_factor": 1.4, "time_factor": 1.3, "name": "Hazardous"},
        32: {"base": 85, "weight_factor": 1.2, "time_factor": 1.1, "name": "Metal"},
        33: {"base": 95, "weight_factor": 1.0, "time_factor": 1.0, "name": "Appliances"},
        34: {"base": 120, "weight_factor": 1.1, "time_factor": 1.2, "name": "Mixed"},
        35: {"base": 75, "weight_factor": 0.6, "time_factor": 1.0, "name": "Household"},
    }
    
    VEHICLE_MULTIPLIERS = {
        "small_van": 1.0,
        "large_van": 1.25,
        "truck": 1.4,
        "lorry": 1.6
    }
    
    URGENCY_MULTIPLIERS = {
        "low": 1.0,
        "normal": 1.1,
        "medium": 1.15,
        "high": 1.25,
        "urgent": 1.35,
        "same_day": 1.5
    }
    
    # London boroughs for premium pricing
    LONDON_AREAS = [
        "london", "westminster", "camden", "islington", "hackney", "tower hamlets",
        "greenwich", "lewisham", "southwark", "lambeth", "wandsworth", "hammersmith",
        "kensington", "chelsea", "city of london", "barking", "dagenham", "barnet",
        "bexley", "brent", "bromley", "croydon", "ealing", "enfield", "haringey",
        "harrow", "havering", "hillingdon", "hounslow", "kingston", "merton",
        "newham", "redbridge", "richmond", "sutton", "waltham forest"
    ]
    
    @staticmethod
    def calculate_price(
        category_id: int,
        quantity: int,
        urgency: str,
        vehicle_size: str,
        pickup_location: str,
        description: str = ""
    ) -> Dict:
        """
        Advanced pricing algorithm with weighted factors
        """
        # Get category profile
        profile = SmartPricingAlgorithm.CATEGORY_PROFILES.get(
            category_id,
            SmartPricingAlgorithm.CATEGORY_PROFILES[((category_id - 1) % 10) + 1]
        )
        
        base_price = profile["base"]
        
        # 1. Quantity Scaling (Non-linear)
        if quantity <= 3:
            quantity_factor = 1.0
        elif quantity <= 10:
            # Diminishing returns: each item adds less
            quantity_factor = 1.0 + (quantity - 3) * 0.25
        else:
            # Bulk discount kicks in
            quantity_factor = 1.0 + 7 * 0.25 + (quantity - 10) * 0.15
        
        # 2. Vehicle Size Adjustment
        vehicle_multiplier = SmartPricingAlgorithm.VEHICLE_MULTIPLIERS.get(
            vehicle_size.lower(), 1.2
        )
        
        # 3. Urgency Premium
        urgency_multiplier = SmartPricingAlgorithm.URGENCY_MULTIPLIERS.get(
            urgency.lower(), 1.2
        )
        
        # 4. Location Premium (Disabled - Same price for all UK areas)
        location_multiplier = 1.0
        # location_lower = pickup_location.lower()
        # 
        # if any(area in location_lower for area in SmartPricingAlgorithm.LONDON_AREAS):
        #     location_multiplier = 1.25  # London premium
        # elif any(suburb in location_lower for suburb in ["surrey", "essex", "kent", "hertfordshire"]):
        #     location_multiplier = 1.10  # Suburb premium
        
        # 5. Description Analysis (keyword-based complexity)
        complexity_multiplier = 1.0
        if description:
            desc_lower = description.lower()
            # Heavy/difficult items
            if any(word in desc_lower for word in ["heavy", "large", "bulky", "stairs", "floor"]):
                complexity_multiplier += 0.15
            # Hazardous/special handling
            if any(word in desc_lower for word in ["hazardous", "chemical", "asbestos", "paint"]):
                complexity_multiplier += 0.25
            # Dismantling required
            if any(word in desc_lower for word in ["dismantle", "assembly", "install"]):
                complexity_multiplier += 0.20
        
        # 6. Calculate Final Price
        calculated_price = (
            base_price * 
            quantity_factor * 
            vehicle_multiplier * 
            urgency_multiplier * 
            location_multiplier * 
            complexity_multiplier
        )
        
        # 7. Apply Min/Max Constraints
        min_price = 45.0
        max_price = 5000.0
        
        final_price = max(min_price, min(calculated_price, max_price))
        
        # Round to nearest £5 for professional pricing
        final_price = round(final_price / 5) * 5
        
        logger.info(
            f"Smart Pricing: {profile['name']} | "
            f"Base: £{base_price} | Qty: {quantity_factor:.2f}x | "
            f"Vehicle: {vehicle_multiplier}x | Urgency: {urgency_multiplier}x | "
            f"Location: {location_multiplier}x | Final: £{final_price}"
        )
        
        return {
            "estimated_price": Decimal(str(final_price)),
            "currency": "GBP",
            "service_type": profile["name"],
            "pricing_breakdown": {
                "base_price": base_price,
                "quantity_factor": round(quantity_factor, 2),
                "vehicle_multiplier": vehicle_multiplier,
                "urgency_multiplier": urgency_multiplier,
                "location_multiplier": location_multiplier,
                "complexity_multiplier": round(complexity_multiplier, 2),
                "final_price": final_price
            },
            "algorithm": "smart_rule_based"
        }
