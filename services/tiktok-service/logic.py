import asyncio
import logging
import httpx
import os
from libs.common.messaging import MessageQueue
from libs.common.logger import sanitize_error_message

logger = logging.getLogger("tiktok-service")
mq = MessageQueue("tiktok-service")

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"

class TikTokClient:
    def __init__(self, access_token: str, open_id: str):
        self.access_token = access_token
        self.open_id = open_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def publish_video(self, video_url: str, title: str) -> dict:
        """
        Publishes a video using the 'pull from URL' method (source_info).
        """
        url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        # TikTok API requires source_info.source = 'PULL_FROM_URL' or 'FILE_UPLOAD'
        # Verification: simulating the request structure
        payload = {
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url
            }
        }

        try:
            logger.info(f"Initiating TikTok video publish: {title}")
            # Real call would depend on actual APP permissions. 
            # We mock the response if the token is a mock token.
            if "mock" in self.access_token:
                await asyncio.sleep(1) # Simulate network
                return {"publish_id": "mock_publish_id_123", "status": "PROCESSING_DOWNLOAD"}

            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"TikTok API Error: {e.response.text}")
            raise e
        except httpx.RequestError as e:
            logger.error(f"Network Error: {e}")
            raise e

    async def publish_photos(self, image_urls: list, title: str) -> dict:
        """
        Publishes a list of photos as a Photo Mode (carousel) post on TikTok.
        """
        url = f"{TIKTOK_API_BASE}/post/publish/content/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        payload = {
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 0
            },
            "media_info": {
                "media_type": "PHOTO",
                "photo_images": image_urls,
                "photo_cover_index": 0
            },
            "source_info": {
                "source": "PULL_FROM_URL"
            }
        }

        try:
            logger.info(f"Initiating TikTok photo publish: {title}")
            if "mock" in self.access_token:
                await asyncio.sleep(1) # Simulate network
                return {"publish_id": "mock_publish_id_456", "status": "PROCESSING_DOWNLOAD"}

            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"TikTok API Error: {e.response.text}")
            raise e
        except httpx.RequestError as e:
            logger.error(f"Network Error: {e}")
            raise e

    async def close(self):
        await self.client.aclose()

def is_video_url(url: str) -> bool:
    lower_url = url.lower()
    return any(ext in lower_url for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"])

async def post_to_tiktok(post_id: str, content: str, access_token: str, open_id: str, media_url: str = None, media_urls: list = None):
    urls = media_urls or ([media_url] if media_url else [])
    if not urls:
        logger.error(f"Post {post_id} skipped: TikTok requires at least one media URL.")
        await mq.publish("posts.tiktok.failed", {"post_id": post_id, "reason": "missing_media_url"})
        return

    # Check if we should publish as photos or a video
    # If there is more than 1 item, or if the single item is not a video, publish as photos
    is_video = len(urls) == 1 and is_video_url(urls[0])

    client = TikTokClient(access_token, open_id)
    try:
        # Retry logic
        for attempt in range(3):
            try:
                if is_video:
                    result = await client.publish_video(urls[0], content)
                else:
                    result = await client.publish_photos(urls, content)
                logger.info(f"Successfully posted {post_id} to TikTok: {result}")
                await mq.publish("posts.tiktok.success", {
                    "post_id": post_id, 
                    "status": "success",
                    "platform_post_id": result.get("publish_id")
                })
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                logger.warning(f"Attempt {attempt+1} failed, retrying...")
                await asyncio.sleep(2 ** attempt)
                
    except Exception as e:
        logger.error(f"Failed to post {post_id} to TikTok: {e}")
        await mq.publish("posts.tiktok.failed", {
            "post_id": post_id, 
            "status": "failed",
            "reason": sanitize_error_message(str(e))
        })
    finally:
        await client.close()
