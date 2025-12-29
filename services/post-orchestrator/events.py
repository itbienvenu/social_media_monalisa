from libs.common.messaging import MessageQueue
import uuid
from libs.common.serializers import Platform

mq = MessageQueue("post-orchestrator")

import os

S3_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "social-media-content")

async def publish_post_event(post_id: uuid.UUID, platform: Platform, content: str, media_key: str = None, user_id: str = "anonymous"):
    # Construct media_url if key exists
    # Note: In production, this should be a presigned GET URL or a CDN URL.
    # For now, we use the direct MinIO/S3 URL accessible by the implementation services.
    # If services are outside the network, this needs to be an external URL.
    media_url = None
    if media_key:
        media_url = f"{S3_ENDPOINT}/{S3_BUCKET}/{media_key}"

    event = {
        "post_id": str(post_id),
        "platform": platform,
        "content": content,
        "media_key": media_key,
        "media_url": media_url,
        "user_id": user_id
    }
    # Ensure we use the string value of the enum for the topic
    topic_platform = platform.value if hasattr(platform, "value") else str(platform)
    await mq.publish(f"posts.{topic_platform}", event)
