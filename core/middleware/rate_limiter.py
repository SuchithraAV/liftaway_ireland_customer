"""Redis-based rate limiting middleware"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from core.redis_client import get_redis
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting: 100 req/min per IP"""
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health/", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        client_ip = request.client.host
        
        try:
            redis = await get_redis()
            if redis:
                key = f"rate_limit:{client_ip}"
                count = await redis.incr(key)
                
                if count == 1:
                    await redis.expire(key, 60)
                
                if count > 100:
                    logger.warning(f"Rate limit exceeded: {client_ip}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests",
                        headers={"Retry-After": "60"}
                    )
                
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = "100"
                response.headers["X-RateLimit-Remaining"] = str(max(0, 100 - count))
                return response
            else:
                return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            return await call_next(request)
