"""
UTHO Object Storage Upload Utility
Handles file uploads to UTHO Object Storage (S3-compatible)
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os
from fastapi import UploadFile
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# UTHO Object Storage Configuration (S3-compatible)
UTHO_ACCESS_KEY = os.getenv("UTHO_ACCESS_KEY")
UTHO_SECRET_KEY = os.getenv("UTHO_SECRET_KEY")
UTHO_BUCKET = os.getenv("UTHO_BUCKET")
UTHO_ENDPOINT = os.getenv("UTHO_ENDPOINT")
UTHO_BUCKET_URL = os.getenv("UTHO_BUCKET_URL")
UTHO_REGION = os.getenv("UTHO_REGION", "ap-south-1")


def get_s3_client():
    """Create and return UTHO Object Storage client (S3-compatible)"""
    return boto3.client(
        's3',
        endpoint_url=UTHO_ENDPOINT,
        aws_access_key_id=UTHO_ACCESS_KEY,
        aws_secret_access_key=UTHO_SECRET_KEY,
        region_name=UTHO_REGION,
        config=Config(signature_version='s3v4')
    )


async def upload_file_to_s3(
    file: UploadFile,
    customer_id: str,
    file_type: str
) -> Optional[str]:
    """
    Upload a file to UTHO Object Storage bucket under customer's folder
    
    Args:
        file: FastAPI UploadFile object
        customer_id: The customer's UUID for folder organization
        file_type: Type of document for naming (e.g., "issue_image_1")
    
    Returns:
        The object storage key (e.g., issues/uuid/issue_image_1.jpg) or None if upload fails
    """
    if not file or not file.filename:
        return None
    
    try:
        # Get file extension
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        
        # Create object storage key: issues/customer_id/file_type.extension
        object_key = f"issues/{customer_id}/{file_type}.{file_extension}"
        
        # Read file content
        file_content = await file.read()
        
        # Reset file pointer for potential re-read
        await file.seek(0)
        
        # Get object storage client
        storage_client = get_s3_client()
        
        # Determine content type
        content_type = file.content_type or 'application/octet-stream'
        
        # Upload to Utho Object Storage
        storage_client.put_object(
            Bucket=UTHO_BUCKET,
            Key=object_key,
            Body=file_content,
            ContentType=content_type,
            ACL='public-read'  # Make files publicly accessible
        )
        
        # Return the object key (will be converted to full URL later)
        return object_key
    
    except ClientError as e:
        print(f"Object Storage Upload Error: {e}")
        return None
    except Exception as e:
        print(f"Upload Error: {e}")
        return None


def get_full_url(object_key: str) -> str:
    """
    Convert object storage key to full URL
    
    Args:
        object_key: The object storage key (e.g., issues/uuid/issue_image_1.jpg)
    
    Returns:
        Full URL to the file
    """
    if not object_key:
        return ""
    
    # Remove leading slash if present
    clean_key = object_key.lstrip('/')
    return f"{UTHO_BUCKET_URL}/{clean_key}"


async def delete_file_from_s3(object_key: str) -> bool:
    """
    Delete a file from UTHO Object Storage bucket
    
    Args:
        object_key: The object storage key (e.g., issues/uuid/issue_image_1.jpg)
    
    Returns:
        True if deleted successfully, False otherwise
    """
    if not object_key:
        return False
    
    try:
        storage_client = get_s3_client()
        
        # Remove leading slash if present
        clean_key = object_key.lstrip('/')
        
        storage_client.delete_object(
            Bucket=UTHO_BUCKET,
            Key=clean_key
        )
        return True
    
    except ClientError as e:
        print(f"Object Storage Delete Error: {e}")
        return False
    except Exception as e:
        print(f"Delete Error: {e}")
        return False
