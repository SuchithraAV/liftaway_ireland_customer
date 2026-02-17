import redis.asyncio as redis
from typing import List, Dict, Optional
from uuid import UUID
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import settings
from core.utils.dijkstra import calculate_travel_distance
from core.models import Company
from core.redis_client import get_redis

logger = logging.getLogger(__name__)

class AllocationQueue:
    def __init__(self):
        self.redis_client = None
    
    async def _get_client(self):
        """Get Redis client with fallback"""
        if self.redis_client is None:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def get_technician_location(self, technician_id: UUID) -> Optional[Dict[str, float]]:
        '''Get technician location from Redis'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot get technician location")
                return None
            
            key = f"technician:location:{technician_id}"
            location_data = await client.get(key)
            
            if location_data:
                return json.loads(location_data)
        except Exception as e:
            logger.error(f"Error getting technician location: {e}")
        return None
    
    async def set_technician_location(self, technician_id: UUID, lat: float, lng: float):
        '''Store technician location in Redis with expiry'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot set technician location")
                return
            
            key = f"technician:location:{technician_id}"
            location_data = json.dumps({"lat": lat, "lng": lng, "updated_at": datetime.utcnow().isoformat()})
            await client.setex(key, settings.REDIS_LOCATION_EXPIRE, location_data)
        except Exception as e:
            logger.error(f"Error setting technician location: {e}")
    
    async def calculate_nearest_technicians(
        self,
        customer_lat: float,
        customer_lng: float,
        technician_ids: List[UUID]
    ) -> List[Dict]:
        '''
        Calculate distances to all technicians using Dijkstra
        Returns sorted list of technicians by distance
        '''
        technician_distances = []
        
        for tech_id in technician_ids:
            location = await self.get_technician_location(tech_id)
            
            if location:
                distance = calculate_travel_distance(
                    customer_lat, customer_lng,
                    location['lat'], location['lng']
                )
                
                technician_distances.append({
                    "technician_id": str(tech_id),
                    "distance_km": distance,
                    "lat": location['lat'],
                    "lng": location['lng']
                })
        
        # Sort by distance
        technician_distances.sort(key=lambda x: x['distance_km'])
        return technician_distances
    
    async def create_allocation_queue(self, booking_id: UUID, technician_list: List[Dict]):
        '''Store allocation queue in Redis'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot create allocation queue")
                return
            
            key = f"booking:queue:{booking_id}"
            queue_data = json.dumps({
                "technicians": technician_list,
                "current_index": 0,
                "created_at": datetime.utcnow().isoformat()
            })
            await client.setex(key, 3600, queue_data)  # 1 hour expiry
        except Exception as e:
            logger.error(f"Error creating allocation queue: {e}")
    
    async def get_allocation_queue(self, booking_id: UUID) -> Optional[Dict]:
        '''Retrieve allocation queue from Redis'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot get allocation queue")
                return None
            
            key = f"booking:queue:{booking_id}"
            queue_data = await client.get(key)
            
            if queue_data:
                return json.loads(queue_data)
        except Exception as e:
            logger.error(f"Error getting allocation queue: {e}")
        return None
    
    async def update_queue_index(self, booking_id: UUID, new_index: int):
        '''Update current index in allocation queue'''
        try:
            queue = await self.get_allocation_queue(booking_id)
            if queue:
                client = await self._get_client()
                if not client:
                    logger.warning("Redis unavailable, cannot update queue index")
                    return
                
                queue['current_index'] = new_index
                key = f"booking:queue:{booking_id}"
                await client.setex(key, 3600, json.dumps(queue))
        except Exception as e:
            logger.error(f"Error updating queue index: {e}")
    
    async def get_next_technician(self, booking_id: UUID) -> Optional[str]:
        '''Get next technician from queue'''
        queue = await self.get_allocation_queue(booking_id)
        
        if not queue:
            return None
        
        current_index = queue['current_index']
        technicians = queue['technicians']
        
        if current_index >= len(technicians):
            return None  # No more technicians
        
        next_tech = technicians[current_index]['technician_id']
        await self.update_queue_index(booking_id, current_index + 1)
        
        return next_tech
    
    async def set_technician_notified(self, booking_id: UUID, technician_id: UUID):
        '''Mark technician as notified with timeout'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot set technician notified")
                return
            
            key = f"booking:notified:{booking_id}:{technician_id}"
            await client.setex(
                key,
                settings.TECHNICIAN_ACCEPT_TIMEOUT_SECONDS,
                "notified"
            )
        except Exception as e:
            logger.error(f"Error setting technician notified: {e}")
    
    async def is_technician_notified(self, booking_id: UUID, technician_id: UUID) -> bool:
        '''Check if technician is currently notified'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot check technician notified")
                return False
            
            key = f"booking:notified:{booking_id}:{technician_id}"
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking technician notified: {e}")
            return False
    
    async def clear_booking_allocation(self, booking_id: UUID):
        '''Clear all allocation data for a booking'''
        try:
            client = await self._get_client()
            if not client:
                logger.warning("Redis unavailable, cannot clear booking allocation")
                return
            
            queue_key = f"booking:queue:{booking_id}"
            await client.delete(queue_key)
            
            # Clear notification keys
            keys = await client.keys(f"booking:notified:{booking_id}:*")
            if keys:
                await client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing booking allocation: {e}")
    
    async def close(self):
        # Don't close shared connection pool
        pass

    async def find_nearest_company(
        self,
        db: AsyncSession,
        customer_lat: float,
        customer_lng: float,
        max_distance_km: float = 50.0
    ) -> Optional[Dict]:
        '''Find nearest active company within max_distance_km'''
        # Query all active companies with location
        result = await db.execute(
            select(Company).where(
                Company.is_active == True,
                Company.lat.isnot(None),
                Company.lng.isnot(None)
            )
        )
        companies = result.scalars().all()
        
        nearest_company = None
        min_distance = float('inf')
        
        for company in companies:
            distance = calculate_travel_distance(
                customer_lat, customer_lng,
                company.lat, company.lng
            )
            
            if distance <= max_distance_km and distance < min_distance:
                min_distance = distance
                nearest_company = {
                    "company_id": company.id,
                    "name": company.name,
                    "distance_km": distance,
                    "lat": company.lat,
                    "lng": company.lng
                }
                
        return nearest_company