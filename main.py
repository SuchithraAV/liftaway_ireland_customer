from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import logging
import traceback

# Core imports
from core.database import engine, Base
from core.redis_client import redis_client
from core.websocket import manager
from core.notifications_websocket import notifications_manager

# Routers
from core.customer_auth import router as customer_auth
from core.routers import ratings, payments, services
from core.routers.categories import router as categories
from core.routers.profile import router as profile
from core.routers.issues import router as issues_router
from core.routers.issue_ratings import router as issue_ratings_router
from core.routers.stripe_payments import router as stripe_router
from core.routers.chat import router as chat_router
from core.routers.notifications import router as notifications_router
from core.routers.customer_payments import router as customer_payments_router
from core.routers.payment_metrics import router as payment_metrics_router
from core.routers.waste_pricing import router as waste_pricing_router
from core.routers.live_location import router as live_location_router, start_location_tracking, stop_location_tracking
from core.routers.payment_success import router as payment_success_router

# Middleware
from core.middleware.rate_limiter import RateLimitMiddleware

# Config
from config import settings

# ------------------------------------------------------------------
# Logging Configuration (Production Safe)
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("customer-api")

# ------------------------------------------------------------------
# Lifespan (Startup / Shutdown)
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Customer API")

    # COMMENTED OUT - Tables already created manually
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    await redis_client.initialize()
    await manager.initialize()
    await notifications_manager.start_subscriber()
    await start_location_tracking()  # Start location tracking services
    
    # Start payment reconciliation background task
    from core.utils.payment_reconciliation import run_reconciliation_loop
    import asyncio
    reconciliation_task = asyncio.create_task(run_reconciliation_loop())
    logger.info("✅ Payment reconciliation started")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Customer API")
    reconciliation_task.cancel()
    await stop_location_tracking()  # Stop location tracking services
    await notifications_manager.stop_subscriber()
    await manager.shutdown()
    await redis_client.close()
    await engine.dispose()

# ------------------------------------------------------------------
# App Initialization
# ------------------------------------------------------------------
app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Customer API",
    version=settings.VERSION,
    lifespan=lifespan,
    debug=False
)

# ------------------------------------------------------------------
# CORS (Production + Development)
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.liftawaysolutions.com",
        "https://liftawaysolutions.com",
        "https://customer.liftawaysolutions.com",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Rate Limiting
# ------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)

# ------------------------------------------------------------------
# Request / Response Logging Middleware
# ------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()
    logger.info(f"📥 {request.method} {request.url}")

    response = await call_next(request)

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"📤 {response.status_code} | {duration:.3f}s")

    return response

# ------------------------------------------------------------------
# Exception Handlers (IMPORTANT – OTP FIX HERE)
# ------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        f"HTTPException {exc.status_code} | {request.method} {request.url} | {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "error_type": "HTTPException",
                "status_code": exc.status_code,
                "error_message": exc.detail,
                "path": str(request.url),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": exc.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error | {request.url}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "error_type": "ValidationError",
                "validation_errors": exc.errors(),
                "path": str(request.url),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": "Request validation failed"
        }
    )

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    error_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    logger.error(f"Response validation error {error_id}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "error_id": error_id,
                "error_type": "ResponseValidationError",
                "validation_errors": exc.errors(),
                "path": str(request.url),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": "Internal response validation error"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # DO NOT swallow HTTPExceptions
    if isinstance(exc, HTTPException):
        raise exc

    error_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    logger.error(
        f"Unhandled error {error_id} | {request.method} {request.url}",
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "error_id": error_id,
                "error_type": type(exc).__name__,
                "path": str(request.url),
                "method": request.method,
                "timestamp": datetime.utcnow().isoformat()
            },
            "message": "Internal server error"
        }
    )

# ------------------------------------------------------------------
# Routers (Single mounting - proxy handles /customer prefix)
# ------------------------------------------------------------------
app.include_router(customer_auth)
app.include_router(ratings, prefix=settings.API_V1_STR)
app.include_router(payments, prefix=settings.API_V1_STR)
app.include_router(profile, prefix=settings.API_V1_STR)
app.include_router(services, prefix=settings.API_V1_STR)
app.include_router(categories, prefix=settings.API_V1_STR)
app.include_router(issues_router, prefix=settings.API_V1_STR)
app.include_router(issue_ratings_router, prefix=settings.API_V1_STR)
app.include_router(stripe_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(customer_payments_router, prefix=settings.API_V1_STR)
app.include_router(payment_metrics_router, prefix=settings.API_V1_STR)
app.include_router(waste_pricing_router, prefix=settings.API_V1_STR)
app.include_router(live_location_router, prefix=settings.API_V1_STR)

# ------------------------------------------------------------------
# Static Files - MUST BE AFTER ROUTERS
# ------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# ------------------------------------------------------------------
# Health & Root
# ------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Breakdown Assistance Customer API",
        "version": settings.VERSION,
        "docs": "/docs",
        "service_type": "Customer Service"
    }

@app.get("/health/")
async def health_check():
    health = {
        "status": "healthy", 
        "service": "customer",
        "environment": settings.ENV
    }
    
    # Check Redis connection
    try:
        is_available = await redis_client.health_check()
        health["redis"] = "connected" if is_available else "disconnected"
        if not is_available:
            health["status"] = "degraded"
    except Exception as e:
        health["redis"] = f"error: {str(e)}"
        health["status"] = "degraded"
    
    # Check Database connection
    try:
        from sqlalchemy import text
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "unhealthy"
    
    return health

# ------------------------------------------------------------------
# WebSockets
# ------------------------------------------------------------------
@app.websocket("/ws/{role}")
async def websocket_endpoint(websocket: WebSocket, role: str):
    await manager.connect(websocket, role)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, role)

# ------------------------------------------------------------------
# Mapbox Token
# ------------------------------------------------------------------
@app.get(f"{settings.API_V1_STR}/mapbox-token")
async def get_mapbox_token():
    token = getattr(settings, "MAPBOX_TOKEN", None)
    return {"mapbox_token": token}
