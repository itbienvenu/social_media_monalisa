import boto3
import os
from botocore.exceptions import ClientError
import logging
import re
import uuid
from fastapi import HTTPException

logger = logging.getLogger("post-orchestrator")

def generate_upload_url(filename: str, user_id: str, content_type: str = "image/jpeg") -> dict:
    """
    Generates a pre-signed PUT URL for uploading to MinIO/S3.
    Returns the public URL where the file will be accessible.
    """
    # Restrict allowed content-types
    ALLOWED_CONTENT_TYPES = {
        "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/mpeg", "video/quicktime", "video/webm"
    }
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Content-Type not allowed")

    # Validate/sanitize filename (no path separators, reasonable length)
    safe_filename = os.path.basename(filename)
    safe_filename = re.sub(r'[^a-zA-Z0-9_\.-]', '', safe_filename)
    if len(safe_filename) > 100:
        name, ext = os.path.splitext(safe_filename)
        safe_filename = name[:100-len(ext)] + ext

    if not safe_filename or safe_filename in (".", ".."):
        safe_filename = "file"

    # Enforce an object key scheme like uploads/{user_id}/{uuid}_{safe_filename}
    file_uuid = uuid.uuid4()
    object_key = f"uploads/{user_id}/{file_uuid}_{safe_filename}"

    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
        config=boto3.session.Config(signature_version='s3v4')
    )
    
    bucket = os.getenv("MINIO_BUCKET_NAME", "social-media-uploads")
    
    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
             s3_client.create_bucket(Bucket=bucket)
        except Exception as e:
             logger.error(f"Failed to create bucket: {e}")

    # Set public-read policy on the bucket to allow anonymous downloads (resolved 403 Forbidden)
    try:
        import json
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicRead",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"]
                }
            ]
        }
        s3_client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        logger.info(f"Successfully set public-read policy on MinIO bucket: {bucket}")
    except Exception as e:
        logger.error(f"Failed to set public-read policy on bucket {bucket}: {e}")

    try:
        # Create a client pointing to the public URL for presigned generation
        # so the signed Host header matches the browser's Host header.
        public_endpoint = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")
        presign_client = boto3.client(
            "s3",
            endpoint_url=public_endpoint,
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
            config=boto3.session.Config(signature_version='s3v4')
        )

        # Generate presigned URL for uploading
        presigned_url = presign_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': object_key,
                'ContentType': content_type
            },
            ExpiresIn=3600
        )
        
        # The public URL (what we send to Facebook/TikTok)
        # We now use the BASE_URL (API Gateway) + /uploads route
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        
        # Strip trailing slash if present
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        public_url = f"{base_url}/uploads/{bucket}/{object_key}"
        
        return {"upload_url": presigned_url, "public_url": public_url, "key": object_key}
        
    except ClientError as e:
        logger.error(f"S3 Error: {e}")
        return None


def delete_media_files(media_keys: list):
    """
    Deletes the listed media files from the MinIO bucket to free up storage.
    """
    if not media_keys:
        return
        
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "test-value"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "test-value"),
        config=boto3.session.Config(signature_version='s3v4')
    )
    bucket = os.getenv("MINIO_BUCKET_NAME", "social-media-uploads")
    
    for key in media_keys:
        if not key:
            continue
        # Extract object key if it's a full public URL
        # Format: http://<domain>/uploads/<bucket>/uploads/<user_id>/<file>
        obj_key = key
        if str(key).startswith("http"):
            parts = str(key).split(f"/uploads/{bucket}/")
            if len(parts) > 1:
                obj_key = parts[1]
            else:
                # Try general fallback to extract starting from "uploads/"
                match = re.search(r'uploads/.*', str(key))
                if match:
                    obj_key = match.group(0)
        
        try:
            s3_client.delete_object(Bucket=bucket, Key=obj_key)
            logger.info(f"Successfully deleted local media file from MinIO: {obj_key}")
        except Exception as e:
            logger.error(f"Failed to delete media file {obj_key} from MinIO: {e}")
