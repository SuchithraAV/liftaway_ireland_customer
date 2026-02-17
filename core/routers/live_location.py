"""
High-Performance Realtime Location Tracking Backend
FastAPI + WebSockets + Redis Pub/Sub + Mapbox
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from typing import Dict, Set, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import asyncio
import logging
from core.redis_client import redis_client
from core.dependencies import get_current_customer, get_current_driver
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["Live Location Tracking"])

# ============================================================================
# MODELS
# ============================================================================

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    heading: Optional[float] = None  # Direction in degrees (0-360)
    speed: Optional[float] = None  # Speed in km/h
    accuracy: Optional[float] = None  # GPS accuracy in meters
    timestamp: Optional[str] = None

class LocationResponse(BaseModel):
    rider_id: str
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: str
    mapbox_token: str  # Sent only to authenticated clients

# ============================================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================================

class LocationConnectionManager:
    """Manages WebSocket connections for realtime location tracking"""
    
    def __init__(self):
        # rider_id -> Set of WebSocket connections tracking this rider
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> rider_id mapping for cleanup
        self.connection_to_rider: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
    
    async def connect_tracker(self, websocket: WebSocket, rider_id: str):
        """Customer connects to track a rider"""
        await websocket.accept()
        async with self._lock:
            if rider_id not in self.active_connections:
                self.active_connections[rider_id] = set()
            self.active_connections[rider_id].add(websocket)
            self.connection_to_rider[websocket] = rider_id
        logger.info(f"Tracker connected to rider {rider_id}. Total trackers: {len(self.active_connections[rider_id])}")
    
    async def disconnect_tracker(self, websocket: WebSocket):
        """Customer disconnects from tracking"""
        async with self._lock:
            rider_id = self.connection_to_rider.pop(websocket, None)
            if rider_id and rider_id in self.active_connections:
                self.active_connections[rider_id].discard(websocket)
                if not self.active_connections[rider_id]:
                    del self.active_connections[rider_id]
                logger.info(f"Tracker disconnected from rider {rider_id}")
    
    async def broadcast_location(self, rider_id: str, location_data: dict):
        """Broadcast location update to all trackers of this rider"""
        if rider_id not in self.active_connections:
            return
        
        disconnected = []
        for websocket in self.active_connections[rider_id].copy():
            try:
                await websocket.send_json(location_data)
            except Exception as e:
                logger.warning(f"Failed to send to tracker: {e}")
                disconnected.append(websocket)
        
        # Cleanup disconnected sockets
        for ws in disconnected:
            await self.disconnect_tracker(ws)
    
    def get_tracker_count(self, rider_id: str) -> int:
        """Get number of active trackers for a rider"""
        return len(self.active_connections.get(rider_id, set()))

location_manager = LocationConnectionManager()

# ============================================================================
# REDIS PUB/SUB HANDLER
# ============================================================================

class RedisLocationSubscriber:
    """Handles Redis Pub/Sub for location broadcasting"""
    
    def __init__(self):
        self.pubsub = None
        self.subscriber_task = None
        self.active_channels: Set[str] = set()
    
    async def start(self):
        """Start Redis Pub/Sub subscriber"""
        if self.subscriber_task:
            return
        client = redis_client.get_client()
        if not client:
            logger.warning("Redis not available, Pub/Sub disabled")
            return
        self.pubsub = client.pubsub()
        self.subscriber_task = asyncio.create_task(self._listen())
        logger.info("Redis location subscriber started")
    
    async def stop(self):
        """Stop Redis Pub/Sub subscriber"""
        if self.subscriber_task:
            self.subscriber_task.cancel()
            try:
                await self.subscriber_task
            except asyncio.CancelledError:
                pass
        if self.pubsub:
            await self.pubsub.close()
        logger.info("Redis location subscriber stopped")
    
    async def subscribe_to_rider(self, rider_id: str):
        """Subscribe to rider location updates"""
        channel = f"rider:{rider_id}:location"
        if channel not in self.active_channels:
            await self.pubsub.subscribe(channel)
            self.active_channels.add(channel)
            logger.info(f"Subscribed to {channel}")
    
    async def unsubscribe_from_rider(self, rider_id: str):
        """Unsubscribe from rider location updates"""
        channel = f"rider:{rider_id}:location"
        if channel in self.active_channels:
            await self.pubsub.unsubscribe(channel)
            self.active_channels.discard(channel)
            logger.info(f"Unsubscribed from {channel}")
    
    async def _listen(self):
        """Listen for Redis Pub/Sub messages"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode()
                    rider_id = channel.split(":")[1]
                    data = json.loads(message["data"])
                    # Broadcast to all WebSocket trackers
                    await location_manager.broadcast_location(rider_id, data)
        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
        except Exception as e:
            logger.error(f"Redis subscriber error: {e}", exc_info=True)

redis_subscriber = RedisLocationSubscriber()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def validate_websocket_token(websocket: WebSocket) -> Optional[dict]:
    """Validate WebSocket connection token"""
    try:
        # Get token from query params or headers
        token = websocket.query_params.get("token")
        if not token:
            # Try to get from headers
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return None
        
        # Validate token (implement your JWT validation here)
        # For now, we'll accept any token - replace with actual validation
        return {"user_id": "validated_user", "token": token}
    
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        await websocket.close(code=4001, reason="Invalid token")
        return None

async def store_location_in_redis(rider_id: str, location: LocationUpdate) -> dict:
    """Store latest location in Redis"""
    location_data = {
        "rider_id": rider_id,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "heading": location.heading,
        "speed": location.speed,
        "accuracy": location.accuracy,
        "timestamp": location.timestamp or datetime.utcnow().isoformat(),
        "geojson": {
            "type": "Point",
            "coordinates": [location.longitude, location.latitude]
        }
    }
    
    # Store in Redis with 1 hour expiry
    key = f"rider:{rider_id}:location"
    client = redis_client.get_client()
    if client:
        await client.setex(
            key,
            3600,  # 1 hour TTL
            json.dumps(location_data)
        )
    
    return location_data

async def get_location_from_redis(rider_id: str) -> Optional[dict]:
    """Get latest location from Redis"""
    key = f"rider:{rider_id}:location"
    client = redis_client.get_client()
    if not client:
        return None
    data = await client.get(key)
    if data:
        return json.loads(data)
    return None

async def publish_location_update(rider_id: str, location_data: dict):
    """Publish location update to Redis Pub/Sub"""
    channel = f"rider:{rider_id}:location"
    client = redis_client.get_client()
    if client:
        await client.publish(channel, json.dumps(location_data))

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/ws/riders/{rider_id}/send")
async def rider_location_sender(websocket: WebSocket, rider_id: str):
    """
    Rider sends GPS updates via WebSocket
    ws://localhost:8000/api/location/ws/riders/{rider_id}/send?token=xxx
    """
    # Validate token
    user = await validate_websocket_token(websocket)
    if not user:
        return
    
    await websocket.accept()
    logger.info(f"Rider {rider_id} connected for sending location")
    
    try:
        while True:
            # Receive location update from rider
            data = await websocket.receive_json()
            
            try:
                location = LocationUpdate(**data)
                
                # Store in Redis
                location_data = await store_location_in_redis(rider_id, location)
                
                # Publish to Redis Pub/Sub for broadcasting
                await publish_location_update(rider_id, location_data)
                
                # Send acknowledgment
                await websocket.send_json({
                    "status": "success",
                    "message": "Location updated",
                    "trackers": location_manager.get_tracker_count(rider_id)
                })
                
            except Exception as e:
                logger.error(f"Error processing location update: {e}")
                await websocket.send_json({
                    "status": "error",
                    "message": str(e)
                })
    
    except WebSocketDisconnect:
        logger.info(f"Rider {rider_id} disconnected")
    except Exception as e:
        logger.error(f"Rider WebSocket error: {e}", exc_info=True)

@router.websocket("/ws/riders/{rider_id}/track")
async def customer_location_tracker(websocket: WebSocket, rider_id: str):
    """
    Customer tracks rider location via WebSocket
    ws://localhost:8000/api/location/ws/riders/{rider_id}/track?token=xxx
    """
    # Validate token
    user = await validate_websocket_token(websocket)
    if not user:
        return
    
    # Connect tracker
    await location_manager.connect_tracker(websocket, rider_id)
    
    # Subscribe to Redis channel for this rider
    await redis_subscriber.subscribe_to_rider(rider_id)
    
    try:
        # Send initial location if available
        initial_location = await get_location_from_redis(rider_id)
        if initial_location:
            initial_location["mapbox_token"] = settings.MAPBOX_TOKEN
            await websocket.send_json(initial_location)
        else:
            await websocket.send_json({
                "status": "waiting",
                "message": "Waiting for rider location",
                "mapbox_token": settings.MAPBOX_TOKEN
            })
        
        # Keep connection alive and handle pings
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if message == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "keepalive"})
    
    except WebSocketDisconnect:
        logger.info(f"Customer disconnected from tracking rider {rider_id}")
    except Exception as e:
        logger.error(f"Tracker WebSocket error: {e}", exc_info=True)
    finally:
        await location_manager.disconnect_tracker(websocket)
        # Unsubscribe if no more trackers
        if location_manager.get_tracker_count(rider_id) == 0:
            await redis_subscriber.unsubscribe_from_rider(rider_id)

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@router.get("/riders/{rider_id}/location", response_model=LocationResponse)
async def get_rider_location(rider_id: str, current_user = Depends(get_current_customer)):
    """
    Get latest rider location from Redis
    Returns location with Mapbox token for authenticated users
    """
    location_data = await get_location_from_redis(rider_id)
    
    if not location_data:
        raise HTTPException(status_code=404, detail="Rider location not found")
    
    # Add Mapbox token for authenticated users
    location_data["mapbox_token"] = settings.MAPBOX_TOKEN
    
    return LocationResponse(**location_data)

@router.post("/riders/{rider_id}/location")
async def update_rider_location(
    rider_id: str,
    location: LocationUpdate,
    current_driver = Depends(get_current_driver)
):
    """
    Backup REST endpoint for riders to update location
    Use WebSocket for realtime updates instead
    """
    # Store in Redis
    location_data = await store_location_in_redis(rider_id, location)
    
    # Publish to Redis Pub/Sub
    await publish_location_update(rider_id, location_data)
    
    return {
        "status": "success",
        "message": "Location updated",
        "trackers": location_manager.get_tracker_count(rider_id),
        "data": location_data
    }

@router.get("/riders/{rider_id}/trackers")
async def get_tracker_count(rider_id: str):
    """Get number of active trackers for a rider"""
    return {
        "rider_id": rider_id,
        "active_trackers": location_manager.get_tracker_count(rider_id)
    }

# ============================================================================
# STARTUP/SHUTDOWN HANDLERS
# ============================================================================

async def start_location_tracking():
    """Start location tracking services"""
    await redis_subscriber.start()
    logger.info("Location tracking services started")

async def stop_location_tracking():
    """Stop location tracking services"""
    await redis_subscriber.stop()
    logger.info("Location tracking services stopped")
