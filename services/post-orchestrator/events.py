from libs.common.messaging import MessageQueue
import uuid
from libs.common.serializers import Platform

mq = MessageQueue("post-orchestrator")

import os

S3_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
S3_BUCKET = os.getenv("MINIO_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME") or "uploads"

async def publish_post_event(post_id: uuid.UUID, platform: Platform, content: str, media_key: str = None, user_id: str = "anonymous", media_keys: list = None, is_reel: bool = False, facebook_page_id: str = None, target_id: str = None):
    mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"
    public_base_url = os.getenv("PUBLIC_BASE_URL")
    if not mock_mode and not public_base_url:
        raise ValueError("PUBLIC_BASE_URL environment variable is required in non-mock mode to build internet-reachable media URLs for external platforms.")
        
    base_url = public_base_url or "http://localhost:8000"
    if base_url.endswith("/"):
        base_url = base_url[:-1]

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
        obj_key = key
        if key.startswith("http://") or key.startswith("https://"):
            parts = key.split(f"/uploads/{S3_BUCKET}/")
            if len(parts) > 1:
                obj_key = parts[1].split("?")[0]
            else:
                import re
                match = re.search(r'uploads/.*', key)
                if match:
                    obj_key = match.group(0).split("?")[0]
        
        from libs.common.signatures import sign_url_path
        exp, sig = sign_url_path(S3_BUCKET, obj_key)
        url = f"{base_url}/uploads/{S3_BUCKET}/{obj_key}?exp={exp}&sig={sig}"
        media_urls.append(url)

    if media_urls:
        media_url = media_urls[0]

    platform_str = platform.value if hasattr(platform, "value") else str(platform)
    
    instagram_account_id = None
    linkedin_urn = None
    tiktok_open_id = None
    
    if target_id:
        if platform_str == "facebook":
            facebook_page_id = target_id
        elif platform_str == "instagram":
            instagram_account_id = target_id
        elif platform_str == "linkedin":
            linkedin_urn = target_id
        elif platform_str == "tiktok":
            tiktok_open_id = target_id

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
        "facebook_page_id": facebook_page_id,
        "instagram_account_id": instagram_account_id,
        "linkedin_urn": linkedin_urn,
        "tiktok_open_id": tiktok_open_id
    }
    await mq.publish(f"posts.{platform_str}", event)
