"""
Production-Ready Twilio Verify Service
Handles SMS OTP verification using Twilio Verify API
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import settings
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class TwilioVerifyService:
    """Twilio Verify service for sending and verifying OTPs via SMS"""
    
    def __init__(self):
        """Initialize Twilio client with credentials from environment"""
        try:
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                raise ValueError("Twilio credentials not configured")
            
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            self.service_sid = settings.TWILIO_VERIFY_SERVICE_SID
            logger.info("✅ Twilio Verify service initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twilio client: {e}")
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
            # Validate phone number format
            if not phone_number.startswith('+'):
                return {
                    "success": False,
                    "error": "Phone number must be in E.164 format (e.g., +919059658735)",
                    "phone_number": phone_number
                }
            
            verification = self.client.verify.v2.services(
                self.service_sid
            ).verifications.create(
                to=phone_number,
                channel=channel
            )
            
            logger.info(f"📱 OTP sent to {phone_number}, status: {verification.status}")
            
            return {
                "success": True,
                "message": "OTP sent successfully",
                "status": verification.status,
                "phone_number": phone_number,
                "channel": channel
            }
            
        except TwilioRestException as e:
            logger.error(f"❌ Twilio error sending OTP to {phone_number}: {e.msg} (Code: {e.code})")
            
            # Handle specific error codes
            error_messages = {
                60200: "Invalid phone number format",
                60203: "Maximum send attempts reached. Please try again later",
                60212: "Too many requests. Please wait before trying again",
                60410: "Phone number is not verified (Twilio trial account limitation)"
            }
            
            return {
                "success": False,
                "error": error_messages.get(e.code, e.msg),
                "error_code": e.code,
                "phone_number": phone_number
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error sending OTP to {phone_number}: {e}")
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
                f"🔐 OTP verification for {phone_number}: {verification_check.status}"
            )
            
            return {
                "success": is_approved,
                "status": verification_check.status,
                "phone_number": phone_number,
                "message": "OTP verified successfully" if is_approved else "Invalid or expired OTP"
            }
            
        except TwilioRestException as e:
            logger.error(f"❌ Twilio error verifying OTP for {phone_number}: {e.msg} (Code: {e.code})")
            
            # Handle specific error codes
            error_messages = {
                60200: "Invalid phone number format",
                60202: "Maximum check attempts reached",
                60203: "Maximum send attempts reached",
                60410: "Phone number is not verified (Twilio trial account limitation)"
            }
            
            return {
                "success": False,
                "error": error_messages.get(e.code, e.msg),
                "error_code": e.code,
                "status": "failed",
                "phone_number": phone_number
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error verifying OTP for {phone_number}: {e}")
            return {
                "success": False,
                "error": "Failed to verify OTP. Please try again.",
                "status": "failed",
                "phone_number": phone_number
            }

# Singleton instance
try:
    twilio_service = TwilioVerifyService()
except Exception as e:
    logger.warning(f"⚠️ Twilio service not available: {e}")
    twilio_service = None
