from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from core.database import get_db
from core.models import Issue, Customer, Driver, ChatMessage, Notification
from core.schemas import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse, ChatStatusResponse
from core.dependencies import get_current_customer
from core.chat_websocket import chat_manager
from core.notifications_websocket import notifications_manager
from core.utils.security import decode_token
from core.utils.encryption import encrypt_message, decrypt_message, is_encrypted
from typing import List
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


async def get_user_from_token(token: str, db: AsyncSession):
    """Validate JWT token and return user info"""
    payload = decode_token(token)
    
    if payload is None or payload.get("type") != "access":
        return None, None, None
    
    user_id = payload.get("sub")
    role = payload.get("role")
    
    if not user_id or not role:
        return None, None, None
    
    # Verify user exists
    if role == "customer":
        result = await db.execute(select(Customer).where(Customer.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user_id, "customer", user
    elif role == "driver":
        result = await db.execute(select(Driver).where(Driver.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user_id, "driver", user
    
    return None, None, None


async def validate_chat_access(issue_id: str, user_id: str, user_type: str, db: AsyncSession):
    """Validate that user has access to the chat for this issue"""
    result = await db.execute(select(Issue).where(Issue.id == UUID(issue_id)))
    issue = result.scalar_one_or_none()
    
    if not issue:
        return None, "Issue not found"
    
    # Check if user is participant
    if user_type == "customer":
        if str(issue.customer_id) != user_id:
            return None, "Not authorized to access this chat"
    elif user_type == "driver":
        if str(issue.assigned_driver_id) != user_id:
            return None, "Not authorized to access this chat"
    
    return issue, None


@router.websocket("/ws/{issue_id}")
async def chat_websocket(
    websocket: WebSocket,
    issue_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time chat.
    Connection URL: /chat/ws/{issue_id}?token=<jwt_token>
    
    Messages are encrypted on client side and stored encrypted.
    Server never decrypts messages.
    """
    # Get database session
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        # Validate token and get user
        user_id, user_type, user = await get_user_from_token(token, db)
        
        if not user_id:
            await websocket.close(code=4003)  # Unauthorized
            return
        
        # Validate access to this issue
        issue, error = await validate_chat_access(issue_id, user_id, user_type, db)
        
        if error:
            await websocket.close(code=4003)
            return
        
        # Check if issue is completed - no new connections allowed
        if issue.status == "completed":
            await websocket.accept()
            await websocket.send_text('{"type": "error", "message": "Chat is closed. Issue has been completed."}')
            await websocket.close(code=4001)
            return
        
        # Check if issue is assigned (chat only available when driver is assigned)
        if issue.status == "pending" or issue.assigned_driver_id is None:
            await websocket.accept()
            await websocket.send_text('{"type": "error", "message": "Chat not available. Waiting for driver assignment."}')
            await websocket.close(code=4002)
            return
        
        # Connect to chat room
        await chat_manager.connect(issue_id, websocket, user_id, user_type)
        
        try:
            while True:
                # Receive plain text message from client
                received_msg = await websocket.receive_text()
                
                # Handle ping/pong for keepalive
                if received_msg == "ping":
                    await websocket.send_text("pong")
                    continue
                
                # Re-check issue status before processing message
                from core.database import AsyncSessionLocal
                async with AsyncSessionLocal() as msg_db:
                    result = await msg_db.execute(select(Issue).where(Issue.id == UUID(issue_id)))
                    current_issue = result.scalar_one_or_none()
                    
                    if not current_issue or current_issue.status == "completed":
                        await websocket.send_text('{"type": "chat_closed", "message": "Chat is closed. Issue has been completed."}')
                        await websocket.close(code=4001)
                        break
                    
                    # Encrypt the message using AES-256-GCM with SHA-256 derived key
                    encrypted_text = encrypt_message(received_msg, issue_id)
                    
                    # Save encrypted message to database
                    chat_message = ChatMessage(
                        issue_id=UUID(issue_id),
                        sender_id=UUID(user_id),
                        sender_type=user_type,
                        encrypted_text=encrypted_text
                    )
                    msg_db.add(chat_message)
                    await msg_db.commit()
                    await msg_db.refresh(chat_message)
                    
                    # Broadcast the original plain text message to other participants
                    # (they receive it in real-time, no need to decrypt)
                    await chat_manager.broadcast_chat_message(
                        issue_id=issue_id,
                        sender_id=user_id,
                        sender_type=user_type,
                        encrypted_text=received_msg,  # Send plain text for real-time display
                        message_id=str(chat_message.id),
                        exclude_websocket=websocket
                    )
                    
                    # Best-effort: persist a notification for the other participant
                    try:
                        # Determine recipient based on sender type
                        if user_type == 'customer':
                            recipient_id = current_issue.assigned_driver_id
                            recipient_type = 'driver'
                        else:
                            recipient_id = current_issue.customer_id
                            recipient_type = 'customer'

                        if recipient_id:
                            sender_name = getattr(user, 'full_name', None) if user is not None else None
                            note = Notification(
                                user_id=recipient_id,
                                user_type=recipient_type,
                                title='New message',
                                message=f'{sender_name or user_type.capitalize()}: {received_msg[:50]}{"..." if len(received_msg) > 50 else ""}',
                                data={"issue_id": str(current_issue.id), "message_id": str(chat_message.id), "from": user_type}
                            )
                            msg_db.add(note)
                            await msg_db.commit()
                            await msg_db.refresh(note)
                            
                            # Push live notification via WebSocket
                            try:
                                await notifications_manager.send_notification(
                                    recipient_type, str(recipient_id),
                                    {"id": str(note.id), "title": note.title, "message": note.message, "data": note.data, "is_read": False, "created_at": note.created_at.isoformat() if note.created_at else None}
                                )
                            except Exception:
                                pass
                    except Exception:
                        try:
                            await msg_db.rollback()
                        except Exception:
                            pass
        
        except WebSocketDisconnect:
            chat_manager.disconnect(issue_id, websocket)
            await chat_manager.broadcast_system_message(
                issue_id,
                f"{user_type.capitalize()} left the chat"
            )
        except Exception as e:
            logger.error(f"WebSocket error for issue {issue_id}: {e}")
            chat_manager.disconnect(issue_id, websocket)


@router.get("/history/{issue_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get chat history for an issue (customer endpoint). Messages are decrypted before returning."""
    # Validate issue access
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.customer_id != current_customer.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this chat")
    
    # Get chat messages
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.issue_id == issue_id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()
    
    # Decrypt messages before returning
    decrypted_messages = []
    for msg in messages:
        try:
            # Decrypt the message using the issue ID
            decrypted_text = decrypt_message(msg.encrypted_text, str(issue_id))
        except Exception as e:
            logger.error(f"Failed to decrypt message {msg.id}: {e}")
            decrypted_text = "[Unable to decrypt message]"
        
        decrypted_messages.append(
            ChatMessageResponse(
                id=msg.id,
                issue_id=msg.issue_id,
                sender_id=msg.sender_id,
                sender_type=msg.sender_type,
                text=decrypted_text,  # Return decrypted text
                created_at=msg.created_at
            )
        )
    
    return ChatHistoryResponse(
        issue_id=issue_id,
        messages=decrypted_messages,
        is_chat_active=issue.status != "completed"
    )


@router.get("/status/{issue_id}", response_model=ChatStatusResponse)
async def get_chat_status(
    issue_id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get chat status for an issue (customer endpoint)"""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.customer_id != current_customer.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this chat")
    
    is_active = issue.status not in ["completed", "pending"] and issue.assigned_driver_id is not None
    
    if issue.status == "completed":
        message = "Chat is closed. Issue has been completed."
    elif issue.status == "pending" or issue.assigned_driver_id is None:
        message = "Chat not available. Waiting for driver assignment."
    else:
        message = "Chat is active."
    
    return ChatStatusResponse(
        issue_id=issue_id,
        is_chat_active=is_active,
        issue_status=issue.status,
        message=message
    )


# ==================== WebSocket Documentation ====================

@router.get("/websocket-info", tags=["Chat"], summary="WebSocket Connection Info")
async def websocket_info():
    r"""
    ## WebSocket Chat Connection Information
    
    This endpoint provides documentation for connecting to the real-time chat WebSocket.
    
    ### WebSocket URL
    ```
    ws://{host}/api/chat/ws/{issue_id}?token={jwt_token}
    ```

        link for test in html (location from driver to customer ws){to work perfectly of websocket use driver/admin port for both websocket url not customer}
    ```
    
     C:\Users\CHAITANYA\Downloads\road assistance seperated\breakdown-technician-admin-backend-clean\static\driver_customer_side_by_side.html
    ```
    link for test in html (chat from driver to customer ws){to work perfectly of websocket use driver/admin port for both websocket url not customer}
    ```
    
    C:\Users\CHAITANYA\Downloads\road assistance seperated\breakdown-technician-admin-backend-clean\issue_chat_interface.html
    ```
    link for test in html (notifications){use driver port for driver and customer port for customer}
    ```
    
    file:///C:/Users/CHAITANYA/Downloads/road%20assistance%20seperated/breakdown-technician-admin-backend-clean/static/notifications_ws_test.html
    ```
    
    ### Connection Parameters
    - **issue_id** (path): UUID of the issue to chat about
    - **token** (query): JWT access token for authentication
    
    ### Authentication
    - Both customers and drivers can connect using their respective JWT tokens
    - The token must be a valid access token (not refresh token)
    - User must be either the customer who created the issue or the assigned driver
    
    ### Chat Availability
    - Chat is only available when issue status is NOT 'pending' or 'completed'
    - A driver must be assigned to the issue before chat is available
    - Chat automatically closes when issue is marked as completed
    
    ### Message Format (Send)
    Simply send the message text as a string. Example:
    ```
    "Hello, I'm on my way!"
    ```
    
    ### Message Format (Receive)
    Messages are received as JSON objects:
    
    **Chat Message:**
    ```json
    {
        "type": "chat",
        "message_id": "uuid",
        "sender_id": "uuid",
        "sender_type": "customer" | "driver",
        "encrypted_text": "message content",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    ```
    
    **System Message:**
    ```json
    {
        "type": "system",
        "message": "Driver joined the chat",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    ```
    
    **Chat Closed:**
    ```json
    {
        "type": "chat_closed",
        "message": "Issue has been completed. Chat closed.",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    ```
    
    **Error:**
    ```json
    {
        "type": "error",
        "message": "Error description"
    }
    ```
    
    ### Keep-Alive
    Send `"ping"` periodically to keep the connection alive. Server responds with `"pong"`.
    
    ### WebSocket Close Codes
    - **1000**: Normal closure
    - **4001**: Chat closed (issue completed)
    - **4002**: Chat not available (issue pending/no driver assigned)
    - **4003**: Unauthorized (invalid token or no access to issue)
    
    ### Example Connection (JavaScript)
    ```javascript
    const ws = new WebSocket('ws://localhost:8001/api/chat/ws/issue-uuid?token=your-jwt-token');
    
    ws.onopen = () => console.log('Connected');
    ws.onmessage = (event) => console.log('Message:', JSON.parse(event.data));
    ws.send('Hello!');
    ```
    """
    return {
        "websocket_url": "ws://{host}/api/chat/ws/{issue_id}?token={jwt_token}",
        "description": "Real-time chat WebSocket for customer-driver communication",
        "parameters": {
            "issue_id": "UUID of the issue (path parameter)",
            "token": "JWT access token (query parameter)"
        },
        "message_types": {
            "send": "Plain text message string",
            "receive": ["chat", "system", "chat_closed", "error"]
        },
        "close_codes": {
            "1000": "Normal closure",
            "4001": "Chat closed (issue completed)",
            "4002": "Chat not available",
            "4003": "Unauthorized"
        },
        "keep_alive": "Send 'ping' to receive 'pong'"
    }