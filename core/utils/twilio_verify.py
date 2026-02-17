"""
Twilio Verify Service for OTP Management
Production-ready implementation with proper error handling
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import settings
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TwilioVerifyService:
    """Twilio Verify service for sending and verifying OTPs"""
    
    def __init__(self):
        """Initialize Twilio client with credentials from settings"""
        try:
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            self.service_sid = settings.TWILIO_VERIFY_SERVICE_SID
            logger.info("Twilio Verify service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            raise
    
    def send_otp(self, phone_number: str, channel: str = 'sms') -> Dict:
        """
        Send OTP to phone number using Twilio Verify
        
        Args:
            phone_number: Phone number in E.164 format (e.g., +919059658735)
            channel: Verification channel ('sms' or 'call')
        
        Returns:
            Dict with success status and message
        """
        try:
            verification = self.client.verify.v2.services(
                self.service_sid
            ).verifications.create(
                to=phone_number,
                channel=channel
            )
            
            logger.info(f"OTP sent to {phone_number}, status: {verification.status}")
            
            return {
                "success": True,
                "message": "OTP sent successfully",
                "status": verification.status,
                "phone_number": phone_number,
                "channel": channel
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending OTP to {phone_number}: {e.msg} (Code: {e.code})")
            return {
                "success": False,
                "error": e.msg,
                "error_code": e.code,
                "phone_number": phone_number
            }
        except Exception as e:
            logger.error(f"Unexpected error sending OTP to {phone_number}: {e}")
            return {
                "success": False,
                "error": "Failed to send OTP. Please try again.",
                "phone_number": phone_number
            }
    
    def verify_otp(self, phone_number: str, otp_code: str) -> Dict:
        """
        Verify OTP using Twilio Verify
        
        Args:
            phone_number: Phone number in E.164 format
            otp_code: OTP code entered by user
        
        Returns:
            Dict with verification status
        """
        try:
            verification_check = self.client.verify.v2.services(
                self.service_sid
            ).verification_checks.create(
                to=phone_number,
                code=otp_code
            )
            
            is_approved = verification_check.status == "approved"
            
            logger.info(
                f"OTP verification for {phone_number}: {verification_check.status}"
            )
            
            return {
                "success": is_approved,
                "status": verification_check.status,
                "phone_number": phone_number,
                "message": "OTP verified successfully" if is_approved else "Invalid or expired OTP"
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio error verifying OTP for {phone_number}: {e.msg} (Code: {e.code})")
            return {
                "success": False,
                "error": e.msg,
                "error_code": e.code,
                "status": "failed",
                "phone_number": phone_number
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying OTP for {phone_number}: {e}")
            return {
                "success": False,
                "error": "Failed to verify OTP. Please try again.",
                "status": "failed",
                "phone_number": phone_number
            }

# Singleton instance
twilio_verify_service = TwilioVerifyService()
