import asyncio
import logging
import httpx
import os
from libs.common.messaging import MessageQueue
from libs.common.logger import sanitize_error_message

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
        
        # Determine media type
        lower_url = media_url.lower()
        is_video = any(ext in lower_url for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"])
        media_type = "REELS" if is_video else "IMAGE"
        
        payload = {
            "caption": caption,
            "access_token": self.access_token
        }
        
        if media_type == "REELS":
            payload["media_type"] = "REELS"
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
            
            # For REELS / VIDEO, wait for status_code to be FINISHED
            if media_type == "REELS":
                status_url = f"{FACEBOOK_GRAPH_URL}/{container_id}"
                status_params = {
                    "fields": "status_code",
                    "access_token": self.access_token
                }
                
                max_retries = 30  # 30 retries * 5 seconds = 150 seconds max wait
                poll_interval = 5
                
                logger.info(f"Polling Instagram container {container_id} status...")
                for attempt in range(max_retries):
                    await asyncio.sleep(poll_interval)
                    status_resp = await self.client.get(status_url, params=status_params)
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    status_code = status_data.get("status_code")
                    
                    logger.info(f"Instagram container {container_id} status_code: {status_code} (attempt {attempt + 1}/{max_retries})")
                    
                    if status_code == "FINISHED":
                        break
                    elif status_code == "ERROR":
                        raise Exception("Instagram video processing failed on their server.")
                    elif status_code == "EXPIRED":
                        raise Exception("Instagram media container expired.")
                else:
                    raise Exception("Instagram video processing timed out.")
                
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

    async def get_post_metrics(self, media_id: str) -> dict:
        """
        Fetches likes, comments, and permalink for an Instagram media object.
        """
        if "mock" in self.access_token:
            return {
                "likes": 42,
                "comments": 7,
                "shares": 0,
                "views": 120,
                "permalink": f"https://instagram.com/p/mock_{media_id}"
            }
            
        url = f"{FACEBOOK_GRAPH_URL}/{media_id}"
        params = {
            "fields": "like_count,comments_count,permalink",
            "access_token": self.access_token
        }
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "likes": data.get("like_count", 0),
                "comments": data.get("comments_count", 0),
                "shares": 0,
                "views": 0,
                "permalink": data.get("permalink")
            }
        except Exception as e:
            logger.error(f"Error fetching IG post metrics for {media_id}: {e}")
            raise e

    async def delete_post(self, media_id: str) -> bool:
        """
        Deletes a media object (post/reel/story) from Instagram.
        """
        if "mock" in self.access_token:
            logger.info(f"Mock delete Instagram post {media_id}")
            return True
            
        url = f"{FACEBOOK_GRAPH_URL}/{media_id}"
        params = {
            "access_token": self.access_token
        }
        try:
            resp = await self.client.delete(url, params=params)
            resp.raise_for_status()
            return resp.json().get("success", False)
        except Exception as e:
            logger.error(f"Error deleting Instagram media {media_id}: {e}")
            raise e

    async def post_carousel(self, media_urls: list, caption: str) -> dict:
        """
        Creates a Carousel post:
        1. Create a container for each item in the carousel with is_carousel_item=True
        2. Wait/Poll for any video containers to finish processing (if any of the items are videos)
        3. Create a parent container of type CAROUSEL with children IDs
        4. Publish the parent container
        """
        if "mock" in self.access_token:
            logger.info(f"Mock publishing carousel with {len(media_urls)} items")
            return {"id": "mock_ig_carousel_id"}

        # Step 1: Create individual containers
        children_ids = []
        for media_url in media_urls:
            container_url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media"
            lower_url = media_url.lower()
            is_video = any(ext in lower_url for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"])
            
            payload = {
                "is_carousel_item": "true",
                "access_token": self.access_token
            }
            if is_video:
                payload["media_type"] = "VIDEO"
                payload["video_url"] = media_url
            else:
                payload["image_url"] = media_url
                
            logger.info(f"Creating carousel item container for {media_url}...")
            resp = await self.client.post(container_url, params=payload)
            resp.raise_for_status()
            container_id = resp.json().get("id")
            children_ids.append(container_id)
            
            # Step 2: Poll status if it's a video
            if is_video:
                status_url = f"{FACEBOOK_GRAPH_URL}/{container_id}"
                status_params = {
                    "fields": "status_code",
                    "access_token": self.access_token
                }
                
                max_retries = 30
                poll_interval = 5
                
                logger.info(f"Polling carousel item video container {container_id} status...")
                for attempt in range(max_retries):
                    await asyncio.sleep(poll_interval)
                    status_resp = await self.client.get(status_url, params=status_params)
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    status_code = status_data.get("status_code")
                    
                    logger.info(f"Carousel item video {container_id} status_code: {status_code} (attempt {attempt + 1}/{max_retries})")
                    
                    if status_code == "FINISHED":
                        break
                    elif status_code == "ERROR":
                        raise Exception("Instagram video processing failed on their server.")
                    elif status_code == "EXPIRED":
                        raise Exception("Instagram media container expired.")
                else:
                    raise Exception("Timed out waiting for Instagram video container processing.")

        # Step 3: Create parent container
        parent_url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media"
        parent_payload = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": self.access_token
        }
        
        logger.info(f"Creating parent CAROUSEL container with children: {children_ids}...")
        resp_parent = await self.client.post(parent_url, params=parent_payload)
        resp_parent.raise_for_status()
        parent_container_id = resp_parent.json().get("id")
        
        # Step 4: Publish parent container
        publish_url = f"{FACEBOOK_GRAPH_URL}/{self.instagram_account_id}/media_publish"
        pub_payload = {
            "creation_id": parent_container_id,
            "access_token": self.access_token
        }
        
        logger.info(f"Publishing parent CAROUSEL container {parent_container_id}...")
        resp_pub = await self.client.post(publish_url, params=pub_payload)
        resp_pub.raise_for_status()
        return resp_pub.json()

    async def close(self):
        await self.client.aclose()


async def post_to_instagram(post_id: str, content: str, access_token: str, target_id: str, media_url: str, media_urls: list = None):
    # Determine the media source
    urls = media_urls or ([media_url] if media_url else [])
    if not urls:
        logger.error("Instagram requires at least one media URL")
        await mq.publish("posts.instagram.failed", {"post_id": post_id, "reason": "missing_media"})
        return

    client = InstagramClient(access_token, target_id)
    try:
        if len(urls) > 1:
            result = await client.post_carousel(urls, content)
        else:
            result = await client.post_media(urls[0], content)
            
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
            "reason": sanitize_error_message(str(e))
        })
    finally:
        await client.close()
