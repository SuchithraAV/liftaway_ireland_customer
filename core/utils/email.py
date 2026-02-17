import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging

from config import settings

logger = logging.getLogger(__name__)

def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return f"{random.randint(100000, 999999)}"

def send_email(email: str, subject: str, body: str) -> bool:
    """Generic function to send email"""
    try:
        # Skip email sending if not configured
        if not settings.EMAIL_ADDRESS or not settings.EMAIL_PASSWORD:
            logger.warning("Email not configured, skipping email send")
            return True  # Return True to not block the flow
        
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Use SMTP with STARTTLS for port 587
        if settings.SMTP_PORT == 587:
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            server.starttls()
        else:
            # Use SMTP_SSL for port 465
            server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT)
        
        server.set_debuglevel(0)
        
        # Handle password with or without spaces
        password = settings.EMAIL_PASSWORD.replace(" ", "")
        
        server.login(settings.EMAIL_ADDRESS, password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def send_verification_email(email: str, otp: str, name: str) -> bool:
    """Send OTP verification email"""
    subject = "Road Assistance - Email Verification"
    body = f"""
    Hi {name},
    
    Welcome to Road Assistance! Please verify your email address using the OTP below:
    
    Your OTP: {otp}
    
    This OTP will expire in 10 minutes.
    
    If you didn't create this account, please ignore this email.
    
    Best regards,
    Road Assistance Team
    """
    return send_email(email, subject, body)

def send_password_reset_email(email: str, otp: str, name: str) -> bool:
    """Send Password Reset OTP email"""
    subject = "Road Assistance - Password Reset Request"
    body = f"""
    Hi {name},
    
    We received a request to reset your password for your Road Assistance account.
    
    Your Password Reset OTP: {otp}
    
    This OTP will expire in 10 minutes.
    
    If you didn't request a password reset, please ignore this email and ensure your account is secure.
    
    Best regards,
    Road Assistance Team
    """
    return send_email(email, subject, body)


def get_otp_expiry() -> datetime:
    """Get OTP expiry time (10 minutes from now)"""
    return datetime.utcnow() + timedelta(minutes=10)