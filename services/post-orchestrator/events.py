from libs.common.messaging import MessageQueue
import uuid
from libs.common.serializers import Platform

mq = MessageQueue("post-orchestrator")

import os

S3_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = os.getenv("MINIO_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "uploads"

async def publish_post_event(post_id: uuid.UUID, platform: Platform, content: str, media_key: str = None, user_id: str = "anonymous", media_keys: list = None, is_reel: bool = False, facebook_page_id: str = None):
    # Construct media_url if key exists
    # Note: In production, this should be a presigned GET URL or a CDN URL.
    # For now, we use the direct MinIO/S3 URL accessible by the implementation services.
    # If services are outside the network, this needs to be an external URL.
    media_url = None
    media_urls = []
    
    # Process multiple media keys if provided, otherwise fallback to single media_key
    keys_to_process = media_keys or ([media_key] if media_key else [])
    
    import boto3
    
    for key in keys_to_process:
        if not isinstance(key, str) or not key:
            continue
        url = None
        if key.startswith("http://") or key.startswith("https://"):
            # If the URL is already pointing to our public gateway (/uploads/), use it directly
            url = key
        else:
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            if base_url.endswith("/"):
                base_url = base_url[:-1]
            url = f"{base_url}/uploads/{S3_BUCKET}/{key}"
        media_urls.append(url)

    if media_urls:
        media_url = media_urls[0]

    platform_str = platform.value if hasattr(platform, "value") else str(platform)
    event = {
        "post_id": str(post_id),
        "platform": platform_str,
        "content": content,
        "media_key": media_key,
        "media_keys": media_keys,
        "media_url": media_url,
        "media_urls": media_urls,
        "user_id": user_id,
        "is_reel": is_reel,
        "facebook_page_id": facebook_page_id
    }
    await mq.publish(f"posts.{platform_str}", event)
