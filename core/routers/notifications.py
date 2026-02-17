from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import Notification
from core.schemas import NotificationResponse
from core.dependencies import get_current_customer
from core.notifications_websocket import notifications_manager
from core.utils.security import decode_token
from typing import List, Tuple
from uuid import UUID

router = APIRouter(tags=["Notifications"])


# ───────────────────────────────────────────────────────────────────────────
# Helper
# ───────────────────────────────────────────────────────────────────────────
async def get_user_from_token_simple(token: str) -> Tuple[str, str]:
    """Decode token and return (user_id, role)."""
    payload = decode_token(token)
    if not payload:
        return None, None
    return payload.get("sub"), payload.get("role")


# ───────────────────────────────────────────────────────────────────────────
# WebSocket endpoint for live notifications
# ───────────────────────────────────────────────────────────────────────────
@router.websocket("/server/customer/notifications")
async def customer_notifications_ws(websocket: WebSocket, token: str = Query(...)):
    """Live notifications for customers.
    Connect: ws://host/api/server/customer/notifications?token=...
    """
    user_id, role = await get_user_from_token_simple(token)
    if not user_id or role != "customer":
        await websocket.accept()
        await websocket.close(code=4003)
        return

    await notifications_manager.connect("customer", user_id, websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notifications_manager.disconnect("customer", user_id, websocket)
    except Exception:
        notifications_manager.disconnect("customer", user_id, websocket)


# ───────────────────────────────────────────────────────────────────────────
# HTTP endpoints
# ───────────────────────────────────────────────────────────────────────────
@router.get('/customer/notifications', response_model=List[NotificationResponse])
async def get_customer_notifications(
    current_customer=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Notification).where(Notification.user_type == 'customer', Notification.user_id == current_customer.id).order_by(Notification.created_at.desc())
        )
        notes = result.scalars().all()
        return [NotificationResponse(**n.__dict__) for n in notes]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch customer notifications: {e}")

@router.put('/customer/notifications/{note_id}/read', response_model=dict)
async def mark_customer_notification_read(note_id: UUID, current_customer=Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Notification).where(Notification.id == note_id, Notification.user_id == current_customer.id))
        note = result.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Notification not found")
        note.is_read = True
        db.add(note)
        await db.commit()
        
        # Push a "remove" event via WebSocket so connected clients hide this notification
        try:
            await notifications_manager.send_notification(
                "customer",
                str(current_customer.id),
                {
                    "type": "notification_read",
                    "id": str(note_id),
                    "action": "remove"
                }
            )
        except Exception:
            pass  # live push failure is non-fatal
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark notification read: {e}")

# Driver-specific endpoints are not hosted in the customer service.
# If you need driver notification endpoints here, implement get_current_driver in this service's dependencies.
