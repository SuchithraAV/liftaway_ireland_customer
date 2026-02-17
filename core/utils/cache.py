"""Redis caching utilities"""
from core.redis_client import get_redis
import json
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

async def get_cached(key: str) -> Optional[Any]:
    """Get value from Redis cache"""
    try:
        redis = await get_redis()
        if not redis:
            return None
        cached = await redis.get(key)
        if cached:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {key}")
        return None
    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None

async def set_cached(key: str, value: Any, ttl: int = 3600):
    """Set value in Redis cache with TTL"""
    try:
        redis = await get_redis()
        if not redis:
            return
        await redis.setex(key, ttl, json.dumps(value, default=str))
        logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.error(f"Cache set error: {e}")

async def delete_cached(key: str):
    """Delete cache key"""
    try:
        redis = await get_redis()
        if not redis:
            return
        await redis.delete(key)
        logger.debug(f"Cache DELETE: {key}")
    except Exception as e:
        logger.error(f"Cache delete error: {e}")

async def invalidate_cache(pattern: str):
    """Invalidate cache keys matching pattern"""
    try:
        redis = await get_redis()
        if not redis:
            return
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
            logger.info(f"Cache INVALIDATED: {len(keys)} keys")
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
