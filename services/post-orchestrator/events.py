from libs.common.messaging import MessageQueue
import uuid
from libs.common.serializers import Platform

mq = MessageQueue("post-orchestrator")

import os

S3_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "social-media-content")

async def publish_post_event(post_id: uuid.UUID, platform: Platform, content: str, media_key: str = None, user_id: str = "anonymous", media_keys: list = None):
    # Construct media_url if key exists
    # Note: In production, this should be a presigned GET URL or a CDN URL.
    # For now, we use the direct MinIO/S3 URL accessible by the implementation services.
    # If services are outside the network, this needs to be an external URL.
    media_url = None
    media_urls = []
    
    # Process multiple media keys if provided, otherwise fallback to single media_key
    keys_to_process = media_keys or ([media_key] if media_key else [])
    
    for key in keys_to_process:
        url = None
        if key.startswith("http://") or key.startswith("https://"):
            # Extract key and bucket from public_url if it's our own
            # public_url format: f"{base_url}/uploads/{bucket}/{object_key}"
            if "/uploads/" in key:
                parts = key.split("/uploads/", 1)[1].split("/", 1)
                if len(parts) == 2:
                    bucket_name, obj_key = parts
                    url = f"{S3_ENDPOINT}/{bucket_name}/{obj_key}"
                else:
                    url = key
            else:
                url = key
        else:
            url = f"{S3_ENDPOINT}/{S3_BUCKET}/{key}"
        media_urls.append(url)

    if media_urls:
        media_url = media_urls[0]

    event = {
        "post_id": str(post_id),
        "platform": platform,
        "content": content,
        "media_key": media_key,
        "media_keys": media_keys,
        "media_url": media_url,
        "media_urls": media_urls,
        "user_id": user_id
    }
    # Ensure we use the string value of the enum for the topic
    topic_platform = platform.value if hasattr(platform, "value") else str(platform)
    await mq.publish(f"posts.{topic_platform}", event)
