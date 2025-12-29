import logging
import os
import aioboto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class StorageClient:
    def __init__(self):
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
        self.access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("S3_SECRET_KEY", "minioadminpassword")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "social-media-media")
        self.session = aioboto3.Session()

    async def upload_file(self, file_data: bytes, object_name: str, content_type: str = "application/octet-stream"):
        async with self.session.client("s3", endpoint_url=self.endpoint_url,
                                       aws_access_key_id=self.access_key,
                                       aws_secret_access_key=self.secret_key) as s3:
            try:
                # Ensure bucket exists
                try:
                    await s3.head_bucket(Bucket=self.bucket_name)
                except ClientError:
                    await s3.create_bucket(Bucket=self.bucket_name)
                
                await s3.put_object(Bucket=self.bucket_name, Key=object_name, Body=file_data, ContentType=content_type)
                logger.info(f"Uploaded {object_name} to {self.bucket_name}")
                
                # Generate URL (assuming public or presigned - for now simple path)
                # In real prod with public read:
                return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"
            except Exception as e:
                logger.error(f"Failed to upload file: {e}")
                raise e
