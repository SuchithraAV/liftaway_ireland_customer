from typing import Dict, Any
from uuid import UUID
import asyncio
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    '''
    Notification service for sending alerts to technicians and customers
    In production, integrate with Firebase, OneSignal, or WebSocket
    '''
    
    async def notify_technician_new_booking(
        self,
        technician_id: UUID,
        booking_id: UUID,
        booking_details: Dict[str, Any]
    ):
        '''Notify technician about new booking request'''
        logger.info(f"Notifying technician {technician_id} about booking {booking_id}")
        
        # In production, send push notification or WebSocket message
        notification = {
            "type": "new_booking",
            "technician_id": str(technician_id),
            "booking_id": str(booking_id),
            "customer_location": {
                "lat": booking_details.get("customer_location_lat"),
                "lng": booking_details.get("customer_location_lng")
            },
            "service_type": booking_details.get("service_type_id"),
            "problem": booking_details.get("problem_description"),
            "estimated_price": booking_details.get("estimated_price"),
            "timeout_seconds": 60
        }
        
        # TODO: Implement actual notification delivery (FCM, WebSocket, etc.)
        await self._send_notification(notification)
    
    async def notify_customer_technician_assigned(
        self,
        customer_id: UUID,
        booking_id: UUID,
        technician_name: str,
        start_otp: str = None,
        completion_otp: str = None
    ):
        '''Notify customer that technician has been assigned'''
        logger.info(f"Notifying customer {customer_id} about technician assignment")
        
        notification = {
            "type": "technician_assigned",
            "customer_id": str(customer_id),
            "booking_id": str(booking_id),
            "technician_name": technician_name,
            "message": f"{technician_name} has accepted your request and is on the way!",
            "start_otp": start_otp,
            "completion_otp": completion_otp
        }
        
        await self._send_notification(notification)
    
    async def notify_customer_no_technician(
        self,
        customer_id: UUID,
        booking_id: UUID
    ):
        '''Notify customer that no technician is available'''
        logger.info(f"Notifying customer {customer_id} about no available technician")
        
        notification = {
            "type": "no_technician",
            "customer_id": str(customer_id),
            "booking_id": str(booking_id),
            "message": "Sorry, no technician is available at the moment. Please try again."
        }
        
        await self._send_notification(notification)
    
    async def notify_status_update(
        self,
        user_id: UUID,
        booking_id: UUID,
        new_status: str
    ):
        '''Notify about booking status change'''
        logger.info(f"Notifying user {user_id} about status change to {new_status}")
        
        notification = {
            "type": "status_update",
            "user_id": str(user_id),
            "booking_id": str(booking_id),
            "status": new_status
        }
        
        await self._send_notification(notification)

    async def notify_customer_completion_otp(
        self,
        customer_id: UUID,
        booking_id: UUID,
        completion_otp: str
    ):
        """Notify customer with the completion OTP (display this to customer when work starts)."""
        logger.info(f"Notifying customer {customer_id} about completion OTP for {booking_id}")
        notification = {
            "type": "completion_otp",
            "customer_id": str(customer_id),
            "booking_id": str(booking_id),
            "completion_otp": completion_otp,
            "message": "Use this OTP to verify completion with the technician when work finishes."
        }
        await self._send_notification(notification)
    
    async def _send_notification(self, notification: Dict[str, Any]):
        '''
        Internal method to send notification
        Implement with your preferred notification service
        '''
        # Simulate async notification sending
        await asyncio.sleep(0.1)
        logger.info(f"Notification sent: {notification}")
        
        # TODO: Integrate with:
        # - Firebase Cloud Messaging (FCM) for mobile push
        # - WebSocket for real-time in-app notifications
        # - SMS gateway for critical alerts
        # - Email service for receipts

notification_service = NotificationService()