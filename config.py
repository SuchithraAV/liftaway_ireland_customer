from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Breakdown Assistance Customer Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    FRONTEND_URL: str = "http://localhost:8000"
    BACKEND_URL: str = "http://localhost:8000"  # Backend domain for Stripe redirects
    ENV: str = "development"  # development or production
    
    # Database
    # Loaded from .env file - no default for security
    DATABASE_URL: str
    
    # Redis
    # Loaded from .env file - no default for security
    REDIS_URL: str
    REDIS_LOCATION_EXPIRE: int = 300
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_CONNECT_TIMEOUT: int = 5
    

    
    # JWT
    # Loaded from .env file - no default for security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    
    # Apple OAuth
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""
    
    # Stripe - Loaded from .env file
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str


    # Email Configuration
    EMAIL_ADDRESS: str = ""
    EMAIL_PASSWORD: str = ""
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    
    # Allocation
    TECHNICIAN_ACCEPT_TIMEOUT_SECONDS: int = 60
    MAX_TECHNICIANS_TO_NOTIFY: int = 5
    
    # UK Map bounds (for validation)
    UK_LAT_MIN: float = 49.9
    UK_LAT_MAX: float = 60.9
    UK_LNG_MIN: float = -8.2
    UK_LNG_MAX: float = 1.8
    
    # Mapbox
    MAPBOX_TOKEN: str = ""
    
    # Twilio Verify
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_VERIFY_SERVICE_SID: str = ""
    
    # Utho Object Storage
    UTHO_ACCESS_KEY: str = ""
    UTHO_SECRET_KEY: str = ""
    UTHO_BUCKET: str = ""
    UTHO_ENDPOINT: str = ""
    UTHO_BUCKET_URL: str = ""
    UTHO_REGION: str = "ap-south-1"
    
    # OpenAI API - MUST be set in environment variables
    OPENAI_API_KEY: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True
    )

settings = Settings()