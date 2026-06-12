import asyncio
import logging
import httpx
import os
import json
from libs.common.messaging import MessageQueue
from libs.common.logger import sanitize_error_message

logger = logging.getLogger("linkedin-service")
mq = MessageQueue("linkedin-service")

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

class LinkedInClient:
    def __init__(self, access_token: str, urn: str):
        self.access_token = access_token
        self.urn = urn
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_profile(self) -> dict:
        """
        Fetch basic profile to get URN if not known.
        """
        if "mock" in self.access_token:
            return {"id": "mock_urn", "localizedFirstName": "Mock", "localizedLastName": "User"}
            
        url = f"{LINKEDIN_API_BASE}/me"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        resp = await self.client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def post_ugc(self, content: str, media_url: str = None) -> dict:
        """
        Create a UGC Post (Text or Image/Video).
        Docs: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api
        """
        url = f"{LINKEDIN_API_BASE}/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        # Author URN must be authenticated user's URN
        author = f"urn:li:person:{self.urn}" if not self.urn.startswith("urn") else self.urn
        
        # Basic Text Share
        share_content = {
            "shareCommentary": {
                "text": content
            },
            "shareMediaCategory": "NONE"
        }
        
        # Note: Real implementation for Media involves 3 steps: Register -> Upload -> Post
        # For this phase, if media_url is provided, we simulate or handle simple link sharing if applicable.
        # But UGC API supports ARTICLE (link) or IMAGE/VIDEO.
        # Simplification: If media_url is present, we treat it as an Article (Link) share for now 
        # unless we implement the full binary upload flow.
        if media_url:
             share_content["shareMediaCategory"] = "ARTICLE"
             share_content["media"] = [{
                 "status": "READY",
                 "description": {"text": content},
                 "originalUrl": media_url,
                 "title": {"text": "Shared Media"}
             }]

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": share_content
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        try:
            logger.info(f"Posting to LinkedIn URN {author}...")
            if "mock" in self.access_token:
                return {"id": "urn:li:share:mock_123"}

            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"LinkedIn API Error: {e.response.text}")
            raise e
        except Exception as e:
            logger.error(f"LinkedIn Error: {e}")
            raise e

    async def close(self):
        await self.client.aclose()


async def post_to_linkedin(post_id: str, content: str, access_token: str, urn: str, media_url: str = None, media_urls: list = None):
    # Fallback to the first item in media_urls if media_url is not specified
    final_url = media_url
    if not final_url and media_urls:
        final_url = media_urls[0]

    client = LinkedInClient(access_token, urn)
    try:
        result = await client.post_ugc(content, final_url)
        logger.info(f"Successfully posted {post_id} to LinkedIn: {result}")
        await mq.publish("posts.linkedin.success", {
            "post_id": post_id, 
            "status": "success", 
            "platform_post_id": result.get("id")
        })
    except Exception as e:
        logger.error(f"Failed to post {post_id} to LinkedIn: {e}")
        await mq.publish("posts.linkedin.failed", {
            "post_id": post_id, 
            "status": "failed", 
            "reason": sanitize_error_message(str(e))
        })
    finally:
        await client.close()
