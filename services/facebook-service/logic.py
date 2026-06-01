import asyncio
import logging
import httpx
import os
from libs.common.messaging import MessageQueue

logger = logging.getLogger("facebook-service")
mq = MessageQueue("facebook-service")

FACEBOOK_API_VERSION = os.getenv("FACEBOOK_API_VERSION", "v18.0")
FACEBOOK_GRAPH_URL = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}"
MOCK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "mock-access-token")
MOCK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "me")

class FacebookClient:
    def __init__(self, access_token: str, page_id: str):
        self.access_token = access_token
        self.page_id = page_id
        self.client = httpx.AsyncClient(timeout=10.0)

    async def post_feed(self, message: str, link: str = None) -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/feed"
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        if link:
            payload["link"] = link

        try:
            logger.info(f"Attempting to post to Facebook Graph API: {url}")
            response = await self.client.post(url, params=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error: {e.response.text}")
            # Mocking success if we are in mock mode and token is mock
            if "mock" in self.access_token:
                logger.warning("Mocking success despite API error (invalid token)")
                return {"id": "mock_fb_post_id_12345"}
            raise e
        except httpx.RequestError as e:
            logger.error(f"Network Error: {e}")
            raise e

    async def get_user_pages(self) -> list[dict]:
        """
        Fetches the pages the user manages and their access tokens.
        """
        url = f"{FACEBOOK_GRAPH_URL}/me/accounts"
        params = {
            "access_token": self.access_token,
            "fields": "id,name,access_token,category"
        }
        try:
            logger.info(f"Fetching user pages from: {url}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error fetching pages: {e.response.text}")
            if "mock" in self.access_token:
                 return [
                     {"id": "mock_page_1", "name": "Mock Page 1", "access_token": "mock_page_token_1", "category": "Test"},
                     {"id": "mock_page_2", "name": "Mock Page 2", "access_token": "mock_page_token_2", "category": "Test"}
                 ]
            raise e
        except httpx.RequestError as e:
            logger.error(f"Network Error: {e}")
            raise e

    async def get_page_posts(self, page_id: str, page_access_token: str) -> list[dict]:
        """
        Fetches posts from a specific page using its access token.
        """
        url = f"{FACEBOOK_GRAPH_URL}/{page_id}/feed"
        params = {
            "access_token": page_access_token,
            "fields": "id,message,created_time,status_type,permalink_url",
            "limit": 20
        }
        try:
            logger.info(f"Fetching page posts from: {url}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error fetching posts: {e.response.text}")
            if "mock" in self.access_token or "mock" in page_access_token:
                 # Mock Data
                 return [
                     {"id": "mock_post_1", "message": "First mock post from historical sync!", "created_time": "2023-12-01T12:00:00+0000", "permalink_url": "http://facebook.com/mock_post_1"},
                     {"id": "mock_post_2", "message": "Another historical post.", "created_time": "2023-11-20T10:00:00+0000", "permalink_url": "http://facebook.com/mock_post_2"}
                 ]
            raise e
        except httpx.RequestError as e:
            logger.error(f"Network Error: {e}")
            raise e

    async def close(self):
        await self.client.aclose()

async def post_to_facebook(post_id: str, content: str, access_token: str, page_id: str):
    # Use the passed token and page_id instead of env vars
    client = FacebookClient(access_token, page_id)
    try:
        # Retry logic
        for attempt in range(3):
            try:
                result = await client.post_feed(content)
                logger.info(f"Successfully posted {post_id} to Facebook: {result}")
                await mq.publish("posts.facebook.success", {
                    "post_id": post_id, 
                    "status": "success",
                    "platform": "facebook",
                    "platform_post_id": result.get("id")
                })
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                logger.warning(f"Attempt {attempt+1} failed, retrying...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
    except Exception as e:
        logger.error(f"Failed to post {post_id} to Facebook after retries: {e}")
        await mq.publish("posts.facebook.failed", {
            "post_id": post_id, 
            "status": "failed",
            "platform": "facebook",
            "reason": str(e)
        })
    finally:
        await client.close()
