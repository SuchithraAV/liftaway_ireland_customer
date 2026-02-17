from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatConnectionManager:
    """
    Manages WebSocket connections for issue-based chat rooms.
    Each issue has its own chat room where customer and driver can communicate.
    """
    
    def __init__(self):
        # Store connections by issue_id: {issue_id: [(websocket, user_id, user_type), ...]}
        self.active_rooms: Dict[str, List[tuple]] = {}
    
    async def connect(self, issue_id: str, websocket: WebSocket, user_id: str, user_type: str):
        """Connect a user to a chat room for a specific issue"""
        await websocket.accept()
        
        if issue_id not in self.active_rooms:
            self.active_rooms[issue_id] = []
        
        self.active_rooms[issue_id].append((websocket, user_id, user_type))
        logger.info(f"Chat WebSocket connected: {user_type} {user_id} to issue {issue_id}")
        
        # Notify room that user joined
        await self.broadcast_system_message(
            issue_id, 
            f"{user_type.capitalize()} joined the chat",
            exclude_websocket=websocket
        )
    
    def disconnect(self, issue_id: str, websocket: WebSocket):
        """Disconnect a user from a chat room"""
        if issue_id in self.active_rooms:
            # Find and remove the connection
            for conn in self.active_rooms[issue_id]:
                if conn[0] == websocket:
                    user_type = conn[2]
                    self.active_rooms[issue_id].remove(conn)
                    logger.info(f"Chat WebSocket disconnected: {user_type} from issue {issue_id}")
                    break
            
            # Clean up empty rooms
            if not self.active_rooms[issue_id]:
                del self.active_rooms[issue_id]
    
    async def broadcast(self, issue_id: str, message: dict, exclude_websocket: WebSocket = None):
        """Broadcast a message to all users in a chat room"""
        if issue_id not in self.active_rooms:
            return
        
        disconnected = []
        for websocket, user_id, user_type in self.active_rooms[issue_id]:
            if websocket == exclude_websocket:
                continue
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {user_type} {user_id}: {e}")
                disconnected.append((websocket, user_id, user_type))
        
        # Remove disconnected connections
        for conn in disconnected:
            self.active_rooms[issue_id].remove(conn)
    
    async def broadcast_system_message(self, issue_id: str, message: str, exclude_websocket: WebSocket = None):
        """Broadcast a system message to all users in a chat room"""
        system_message = {
            "type": "system",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(issue_id, system_message, exclude_websocket)
    
    async def broadcast_chat_message(self, issue_id: str, sender_id: str, sender_type: str, 
                                      encrypted_text: str, message_id: str, exclude_websocket: WebSocket = None):
        """Broadcast a chat message to all users in a chat room"""
        chat_message = {
            "type": "chat",
            "message_id": message_id,
            "sender_id": sender_id,
            "sender_type": sender_type,
            "encrypted_text": encrypted_text,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(issue_id, chat_message, exclude_websocket)
    
    async def close_room(self, issue_id: str):
        """Close a chat room and notify all connected users"""
        if issue_id not in self.active_rooms:
            return
        
        close_message = {
            "type": "chat_closed",
            "message": "Issue has been completed. Chat closed.",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Notify all users in the room
        for websocket, user_id, user_type in self.active_rooms[issue_id]:
            try:
                await websocket.send_text(json.dumps(close_message))
                await websocket.close(code=4001)
            except Exception as e:
                logger.error(f"Error closing websocket for {user_type} {user_id}: {e}")
        
        # Clean up the room
        del self.active_rooms[issue_id]
        logger.info(f"Chat room closed for issue {issue_id}")
    
    def is_user_connected(self, issue_id: str, user_id: str) -> bool:
        """Check if a user is connected to a chat room"""
        if issue_id not in self.active_rooms:
            return False
        
        for _, uid, _ in self.active_rooms[issue_id]:
            if uid == user_id:
                return True
        return False
    
    def get_room_participants(self, issue_id: str) -> List[dict]:
        """Get list of participants in a chat room"""
        if issue_id not in self.active_rooms:
            return []
        
        return [
            {"user_id": user_id, "user_type": user_type}
            for _, user_id, user_type in self.active_rooms[issue_id]
        ]


# Global chat manager instance
chat_manager = ChatConnectionManager()
