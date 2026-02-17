"""
Production-ready Redis client with connection pooling and graceful degradation
"""
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from typing import Optional
import logging
from config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis client with connection pooling"""
    
    _instance: Optional['RedisClient'] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    _available: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize Redis connection pool"""
        if self._pool is not None:
            return
        
        try:
            self._pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=getattr(settings, 'REDIS_MAX_CONNECTIONS', 50),
                socket_timeout=getattr(settings, 'REDIS_SOCKET_TIMEOUT', 5),
                socket_connect_timeout=getattr(settings, 'REDIS_CONNECT_TIMEOUT', 5),
                retry_on_timeout=True,
                decode_responses=True,
                health_check_interval=30
            )
            
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            self._available = True
            logger.info("✅ Redis connection established successfully")
            
        except Exception as e:
            self._available = False
            logger.warning(f"⚠️ Redis unavailable, running in fallback mode: {e}")
    
    async def close(self):
        """Close Redis connection pool"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._pool = None
        self._client = None
        self._available = False
        logger.info("Redis connection closed")
    
    def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance"""
        return self._client if self._available else None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self._available
    
    async def health_check(self) -> bool:
        """Perform health check"""
        if not self._available or not self._client:
            return False
        
        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self._available = False
            return False


# Global singleton instance
redis_client = RedisClient()


async def get_redis() -> Optional[redis.Redis]:
    """Dependency to get Redis client"""
    return redis_client.get_client()
