from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional
import json
import logging
import asyncio
import redis.asyncio as redis
from config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store connections by user role
        self.active_connections: Dict[str, List[WebSocket]] = {
            "admin": [],
            "technician": [],
            "customer": []
        }
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub = None
        self._subscriber_task = None
        self._running = False
        self._redis_available = False
    
    async def initialize(self):
        """Initialize Redis Pub/Sub for multi-instance support"""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            await self._redis_client.ping()
            self._redis_available = True
            self._running = True
            self._subscriber_task = asyncio.create_task(self._subscribe_loop())
            logger.info("✅ WebSocket Redis Pub/Sub initialized")
        except Exception as e:
            self._redis_available = False
            logger.warning(f"⚠️ WebSocket Redis Pub/Sub unavailable, running in local-only mode: {e}")
    
    async def _subscribe_loop(self):
        """Subscribe to Redis channels for cross-instance broadcasting"""
        while self._running:
            try:
                self._pubsub = self._redis_client.pubsub()
                await self._pubsub.subscribe("websocket:broadcast")
                logger.info("✅ Subscribed to websocket:broadcast channel")
                
                async for message in self._pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            role = data.get("role")
                            msg = data.get("message")
                            if role and msg:
                                await self._send_to_local_connections(role, msg)
                        except Exception as e:
                            logger.error(f"Error processing WebSocket Redis message: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket Redis subscriber error, retrying in 5s: {e}")
                await asyncio.sleep(5)
            finally:
                if self._pubsub:
                    try:
                        await self._pubsub.unsubscribe("websocket:broadcast")
                        await self._pubsub.close()
                    except:
                        pass
    
    async def shutdown(self):
        """Shutdown Redis Pub/Sub"""
        self._running = False
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        if self._redis_client:
            await self._redis_client.close()
        logger.info("WebSocket Redis Pub/Sub shutdown")

    async def connect(self, websocket: WebSocket, role: str):
        await websocket.accept()
        if role in self.active_connections:
            self.active_connections[role].append(websocket)
            logger.info(f"WebSocket connected for role: {role}")

    def disconnect(self, websocket: WebSocket, role: str):
        if role in self.active_connections and websocket in self.active_connections[role]:
            self.active_connections[role].remove(websocket)
            logger.info(f"WebSocket disconnected for role: {role}")

    async def _send_to_local_connections(self, role: str, message: dict):
        """Send message to local connections only"""
        if role not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[role]:
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.active_connections[role].remove(conn)
    
    async def send_to_role(self, role: str, message: dict):
        """Send message to all connections of a specific role (broadcasts via Redis)"""
        # Send to local connections
        await self._send_to_local_connections(role, message)
        
        # Broadcast to other instances via Redis
        if self._redis_available and self._redis_client:
            try:
                await self._redis_client.publish("websocket:broadcast", json.dumps({
                    "role": role,
                    "message": message
                }))
            except Exception as e:
                logger.error(f"Failed to publish WebSocket message to Redis: {e}")
                self._redis_available = False
    
    async def send_to_customer(self, customer_id: str, message: dict):
        """Send message to specific customer"""
        message["customer_id"] = customer_id
        await self.send_to_role("customer", message)

    async def broadcast_booking_update(self, booking_data: dict, event_type: str):
        """Broadcast booking updates to admin, technicians, and customers"""
        message = {
            "type": event_type,
            "data": booking_data,
            "timestamp": booking_data.get("updated_at")
        }
        
        # Send to all user types for real-time updates
        await self.send_to_role("admin", message)
        await self.send_to_role("technician", message)
        await self.send_to_role("customer", message)

manager = ConnectionManager()