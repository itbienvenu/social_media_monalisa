import asyncio
import logging
import httpx
import os
from libs.common.messaging import MessageQueue

logger = logging.getLogger("instagram-service")
mq = MessageQueue("instagram-service")

FACEBOOK_API_VERSION = os.getenv("FACEBOOK_API_VERSION", "v18.0")
FACEBOOK_GRAPH_URL = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}"

class InstagramClient:
    def __init__(self, access_token: str, instagram_account_id: str):
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_user_accounts(self) -> list[dict]:
        """
        Fetches connected Instagram Business Accounts via FB Pages.
        """
        url = f"{FACEBOOK_GRAPH_URL}/me/accounts"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,instagram_business_account{id,name,username}"
        }
        if "mock" in self.access_token:
            return [{"id": "mock_ig_123", "name": "Mock IG Business", "page_id": "mock_page_123"}]
            
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            
            # Filter for pages that have an IG business account linked
            ig_accounts = []
            for page in data:
                if page.get("instagram_business_account"):
                    ig = page["instagram_business_account"]
                    ig_accounts.append({
                        "id": ig["id"],
                        "name": ig.get("name") or ig.get("username", "Instagram Account"),
                        "page_id": page["id"] # We might need this, but token is usually User token or Page token
                    })
            return ig_accounts
            
        except Exception as e:
            logger.error(f"Error fetching IG accounts: {e}")
            raise e

    async def get_instagram_posts(self) -> list[dict]:
        """
        Fetches media (posts/reels) from the connected Instagram account.
        """
        url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media"
        params = {
            "access_token": self.access_token,
            "fields": "id,caption,timestamp,media_url,permalink"
        }
        try:
            if "mock" in self.access_token:
                return [
                    {
                        "id": "mock_ig_post_1",
                        "caption": "Throwback Thursday! #tbt",
                        "timestamp": "2026-06-10T12:00:00+0000",
                        "media_url": "https://placehold.co/600x400.png",
                        "permalink": "https://instagram.com/p/mock_ig_post_1"
                    }
                ]
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error fetching IG posts: {e}")
            raise e

    async def post_media(self, media_url: str, caption: str) -> dict:
        """
        2-Step Flow: Create Container -> Publish Container
        """
        # Step 1: Create Container
        container_url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media"
        
        # Determine media type (simplistic)
        media_type = "VIDEO" if media_url.endswith(".mp4") else "IMAGE"
        
        payload = {
            "caption": caption,
            "access_token": self.access_token
        }
        
        if media_type == "VIDEO":
            payload["media_type"] = "VIDEO"
            payload["video_url"] = media_url
        else:
            payload["image_url"] = media_url

        try:
            logger.info(f"Creating IG Media Container for {media_type}...")
            if "mock" in self.access_token:
                 return {"id": "mock_ig_media_id"}

            resp1 = await self.client.post(container_url, params=payload)
            resp1.raise_for_status()
            container_id = resp1.json().get("id")
            
            # Step 2: Publish Container
            publish_url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media_publish"
            pub_payload = {
                "creation_id": container_id,
                "access_token": self.access_token
            }
            
            # Note: For video, we might need to wait for status=FINISHED. 
            # Doing a small sleep here for simplicity, real impl needs polling.
            if media_type == "VIDEO":
                await asyncio.sleep(5) 
                
            logger.info(f"Publishing IG Media Container {container_id}...")
            resp2 = await self.client.post(publish_url, params=pub_payload)
            resp2.raise_for_status()
            
            return resp2.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"IG API Error: {e.response.text}")
            raise e
        except Exception as e:
             logger.error(f"IG Error: {e}")
             raise e

    async def close(self):
        await self.client.aclose()


async def post_to_instagram(post_id: str, content: str, access_token: str, target_id: str, media_url: str):
    if not media_url:
        logger.error("Instagram requires media_url")
        await mq.publish("posts.instagram.failed", {"post_id": post_id, "reason": "missing_media"})
        return

    client = InstagramClient(access_token, target_id)
    try:
        result = await client.post_media(media_url, content)
        logger.info(f"Successfully posted {post_id} to Instagram: {result}")
        await mq.publish("posts.instagram.success", {
            "post_id": post_id, 
            "status": "success", 
            "platform_post_id": result.get("id")
        })
    except Exception as e:
        logger.error(f"Failed to post {post_id} to Instagram: {e}")
        await mq.publish("posts.instagram.failed", {
            "post_id": post_id, 
            "status": "failed", 
            "reason": str(e)
        })
    finally:
        await client.close()
