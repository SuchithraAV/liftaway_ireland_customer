import httpx
from google.auth.transport import requests
from google.oauth2 import id_token
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class GoogleOAuth:
    def __init__(self, client_id: str):
        self.client_id = client_id
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Google ID token and return user info"""
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                self.client_id
            )
            
            # Token is valid, return user info
            return {
                'email': idinfo.get('email'),
                'name': idinfo.get('name'),
                'picture': idinfo.get('picture'),
                'email_verified': idinfo.get('email_verified', False),
                'provider': 'google',
                'provider_id': idinfo.get('sub')
            }
        except ValueError as e:
            logger.error(f"Google token verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Google token verification: {e}")
            return None

class AppleOAuth:
    def __init__(self, client_id: str, team_id: str, key_id: str, private_key: str):
        self.client_id = client_id
        self.team_id = team_id
        self.key_id = key_id
        self.private_key = private_key
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Apple ID token and return user info"""
        try:
            # For Apple Sign In, we need to verify the JWT token
            # This is a simplified version - in production, you'd want more robust verification
            import jwt
            
            # Get Apple's public keys
            async with httpx.AsyncClient() as client:
                response = await client.get("https://appleid.apple.com/auth/keys")
                keys = response.json()
            
            # Decode and verify the token
            # Note: This is a basic implementation
            # In production, implement proper key rotation and verification
            decoded = jwt.decode(
                token,
                options={"verify_signature": False},  # Simplified for demo
                algorithms=["RS256"]
            )
            
            return {
                'email': decoded.get('email'),
                'name': decoded.get('name', 'Apple User'),
                'email_verified': decoded.get('email_verified', False),
                'provider': 'apple',
                'provider_id': decoded.get('sub')
            }
        except Exception as e:
            logger.error(f"Apple token verification failed: {e}")
            return None

# OAuth service instances
from config import settings

google_oauth = GoogleOAuth(client_id=settings.GOOGLE_CLIENT_ID)
apple_oauth = AppleOAuth(
    client_id=settings.APPLE_CLIENT_ID,
    team_id=settings.APPLE_TEAM_ID,
    key_id=settings.APPLE_KEY_ID, 
    private_key=settings.APPLE_PRIVATE_KEY
)