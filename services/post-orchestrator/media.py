import boto3
import os
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger("post-orchestrator")

def generate_upload_url(filename: str, content_type: str = "image/jpeg") -> str:
    """
    Generates a pre-signed PUT URL for uploading to MinIO/S3.
    Returns the public URL where the file will be accessible.
    """
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
                'Key': filename,
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
            
        public_url = f"{base_url}/uploads/{bucket}/{filename}"
        
        return {"upload_url": presigned_url, "public_url": public_url, "key": filename}
        
    except ClientError as e:
        logger.error(f"S3 Error: {e}")
        return None
