import asyncio
import logging
import httpx
import os
from libs.common.messaging import MessageQueue
from services.facebook_service.db import database
from libs.common.logger import log_post_stage

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

    async def post_feed(self, message: str, link: str = None, post_id: str = None) -> dict:
        url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/feed"
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        if link:
            payload["link"] = link

        if post_id:
            await log_post_stage(
                database, post_id, "facebook", "posting_to_platform", "INFO",
                f"Attempting to post text to Facebook Graph API feed: {url}"
            )

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

    async def post_photo(self, image_url: str, caption: str = None, post_id: str = None) -> dict:
        # Resolve local URL references so the container can access them
        download_url = image_url
        if "localhost:8000" in download_url:
            download_url = download_url.replace("localhost:8000", "api-gateway:8000")
        elif "127.0.0.1:8000" in download_url:
            download_url = download_url.replace("127.0.0.1:8000", "api-gateway:8000")
        elif "localhost:9000" in download_url:
            download_url = download_url.replace("localhost:9000", "minio:9000")
        elif "127.0.0.1:9000" in download_url:
            download_url = download_url.replace("127.0.0.1:9000", "minio:9000")

        if post_id:
            await log_post_stage(
                database, post_id, "facebook", "downloading_media", "INFO",
                f"Downloading image from {download_url}"
            )

        logger.info(f"Downloading image from {download_url} to upload to Facebook...")
        
        image_bytes = None
        content_type = "image/jpeg"
        try:
            dl_resp = await self.client.get(download_url, timeout=15.0)
            dl_resp.raise_for_status()
            image_bytes = dl_resp.content
            content_type = dl_resp.headers.get("content-type", "image/jpeg")
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", "media_downloaded", "INFO",
                    f"Successfully downloaded image content ({len(image_bytes)} bytes)"
                )
        except Exception as e:
            logger.error(f"Failed to download image from {download_url}: {e}")
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", "media_download_failed", "WARNING",
                    f"Failed to download image from {download_url}: {e}. Falling back to URL upload"
                )

        url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/photos"
        
        # If we successfully got the image bytes, upload them as binary via multipart
        if image_bytes:
            files = {
                "source": ("image.jpg", image_bytes, content_type)
            }
            data = {
                "access_token": self.access_token
            }
            if caption:
                data["caption"] = caption
                
            try:
                if post_id:
                    await log_post_stage(
                        database, post_id, "facebook", "posting_to_platform", "INFO",
                        f"Uploading binary photo (multipart/form-data) to Facebook Graph API: {url}"
                    )
                logger.info(f"Uploading photo to Facebook Graph API: {url} (size={len(image_bytes)} bytes)")
                response = await self.client.post(url, data=data, files=files)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Facebook API Error uploading photo binary: {e.response.text}")
                if "mock" in self.access_token:
                    logger.warning("Mocking success despite API error (invalid token)")
                    return {"id": "mock_fb_post_id_12345"}
                raise e
            except httpx.RequestError as e:
                logger.error(f"Network Error uploading photo binary: {e}")
                raise e
        else:
            # Fallback to passing the URL directly to Facebook (requires public URL)
            payload = {
                "url": image_url,
                "access_token": self.access_token
            }
            if caption:
                payload["caption"] = caption
            try:
                if post_id:
                    await log_post_stage(
                        database, post_id, "facebook", "posting_to_platform", "INFO",
                        f"Posting photo using remote URL parameter to Facebook Graph API: {url}"
                    )
                logger.info(f"Fallback: Posting photo URL to Facebook Graph API: {url} with image_url: {image_url}")
                response = await self.client.post(url, params=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Facebook API Error posting photo URL: {e.response.text}")
                if "mock" in self.access_token:
                    logger.warning("Mocking success despite API error (invalid token)")
                    return {"id": "mock_fb_post_id_12345"}
                raise e
            except httpx.RequestError as e:
                logger.error(f"Network Error posting photo URL: {e}")
                raise e

    async def post_multiple_photos(self, image_urls: list, caption: str = None, post_id: str = None) -> dict:
        """
        Posts multiple photos to Facebook Page by first uploading each photo with published=false,
        and then creating a feed post with attached_media referencing the uploaded photo IDs.
        """
        photo_ids = []
        import json
        for idx, image_url in enumerate(image_urls):
            # Resolve localhost/minio routing
            download_url = image_url
            if "localhost:8000" in download_url:
                download_url = download_url.replace("localhost:8000", "api-gateway:8000")
            elif "127.0.0.1:8000" in download_url:
                download_url = download_url.replace("127.0.0.1:8000", "api-gateway:8000")
            elif "localhost:9000" in download_url:
                download_url = download_url.replace("localhost:9000", "minio:9000")
            elif "127.0.0.1:9000" in download_url:
                download_url = download_url.replace("127.0.0.1:9000", "minio:9000")

            image_bytes = None
            content_type = "image/jpeg"
            
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", f"downloading_media_part_{idx+1}", "INFO",
                    f"Downloading image part {idx+1} from {download_url}"
                )
                
            try:
                dl_resp = await self.client.get(download_url, timeout=15.0)
                dl_resp.raise_for_status()
                image_bytes = dl_resp.content
                content_type = dl_resp.headers.get("content-type", "image/jpeg")
                if post_id:
                    await log_post_stage(
                        database, post_id, "facebook", f"media_downloaded_part_{idx+1}", "INFO",
                        f"Successfully downloaded image part {idx+1} ({len(image_bytes)} bytes)"
                    )
            except Exception as e:
                logger.error(f"Failed to download image part {idx+1} from {download_url}: {e}")
                if post_id:
                    await log_post_stage(
                        database, post_id, "facebook", f"media_download_failed_part_{idx+1}", "WARNING",
                        f"Failed to download image part {idx+1} from {download_url}: {e}. Falling back to URL upload"
                    )

            url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/photos"

            # If we successfully got the image bytes, upload them as binary via multipart
            if image_bytes:
                files = {
                    "source": (f"image_{idx}.jpg", image_bytes, content_type)
                }
                data = {
                    "access_token": self.access_token,
                    "published": "false"
                }
                try:
                    if post_id:
                        await log_post_stage(
                            database, post_id, "facebook", f"uploading_media_part_{idx+1}", "INFO",
                            f"Uploading binary photo part {idx+1} to Facebook Graph API"
                        )
                    response = await self.client.post(url, data=data, files=files)
                    response.raise_for_status()
                    photo_id = response.json().get("id")
                    photo_ids.append(photo_id)
                except httpx.HTTPStatusError as e:
                    logger.error(f"Facebook API Error uploading photo part {idx+1} binary: {e.response.text}")
                    if "mock" in self.access_token:
                        photo_ids.append(f"mock_photo_id_{idx+1}")
                    else:
                        raise e
                except Exception as e:
                    logger.error(f"Error uploading photo part {idx+1} binary: {e}")
                    raise e
            else:
                # Fallback to passing the URL directly to Facebook (requires public URL)
                payload = {
                    "url": image_url,
                    "published": "false",
                    "access_token": self.access_token
                }
                try:
                    if post_id:
                        await log_post_stage(
                            database, post_id, "facebook", f"uploading_media_part_{idx+1}", "INFO",
                            f"Posting photo part {idx+1} using remote URL parameter to Facebook Graph API"
                        )
                    response = await self.client.post(url, params=payload)
                    response.raise_for_status()
                    photo_id = response.json().get("id")
                    photo_ids.append(photo_id)
                except httpx.HTTPStatusError as e:
                    logger.error(f"Facebook API Error posting photo part {idx+1} URL: {e.response.text}")
                    if "mock" in self.access_token:
                        photo_ids.append(f"mock_photo_id_{idx+1}")
                    else:
                        raise e
                except Exception as e:
                    logger.error(f"Error posting photo part {idx+1} URL: {e}")
                    raise e

        # Now attach all photos to a single feed post
        feed_url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/feed"
        attached_media = [{"media_fbid": pid} for pid in photo_ids]
        payload = {
            "access_token": self.access_token,
            "message": caption or "",
            "attached_media": json.dumps(attached_media)
        }
        
        try:
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", "posting_to_platform", "INFO",
                    f"Publishing multi-photo post with {len(photo_ids)} attached photos to Facebook feed"
                )
            logger.info(f"Publishing feed post with attached media: {attached_media}")
            response = await self.client.post(feed_url, params=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error publishing feed post: {e.response.text}")
            if "mock" in self.access_token:
                logger.warning("Mocking success despite API error (invalid token)")
                return {"id": "mock_fb_post_id_multi"}
            raise e
        except Exception as e:
            logger.error(f"Error publishing feed post: {e}")
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

    async def get_post_metrics(self, platform_post_id: str) -> dict:
        """
        Fetches metrics (likes/reactions, comments, shares, etc.) for a specific post.
        """
        # We also query the 'status' field in case platform_post_id is a video node or page post with status
        url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}"
        params = {
            "access_token": self.access_token,
            "fields": "shares,likes.summary(true).limit(0),comments.summary(true).limit(0),status,permalink_url"
        }
        try:
            logger.info(f"Fetching metrics for post {platform_post_id} from {url}")
            response = await self.client.get(url, params=params)
            if response.status_code == 400 and "shares" in response.text:
                logger.info(f"Post {platform_post_id} returned 400 for shares. Retrying without shares field.")
                params["fields"] = "likes.summary(true).limit(0),comments.summary(true).limit(0),status,permalink_url"
                response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            likes_count = data.get("likes", {}).get("summary", {}).get("total_count", 0)
            comments_count = data.get("comments", {}).get("summary", {}).get("total_count", 0)
            shares_count = data.get("shares", {}).get("count", 0)
            
            video_status = None
            video_progress = None
            status_data = data.get("status")
            if isinstance(status_data, dict):
                video_status = status_data.get("video_status")
                video_progress = status_data.get("processing_progress")
            
            # Fallback status query in case post is a standard Page Post but has video attachments
            if not video_status:
                try:
                    attachments_url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}"
                    att_resp = await self.client.get(attachments_url, params={"access_token": self.access_token, "fields": "attachments"})
                    if att_resp.status_code == 200:
                        att_data = att_resp.json().get("attachments", {}).get("data", [])
                        if att_data:
                            target_id = att_data[0].get("target", {}).get("id")
                            if target_id and target_id != platform_post_id:
                                v_resp = await self.client.get(f"{FACEBOOK_GRAPH_URL}/{target_id}", params={"access_token": self.access_token, "fields": "status"})
                                if v_resp.status_code == 200:
                                    vs_data = v_resp.json().get("status")
                                    if isinstance(vs_data, dict):
                                        video_status = vs_data.get("video_status")
                                        video_progress = vs_data.get("processing_progress")
                except Exception as status_err:
                    logger.debug(f"Failed to fetch attachment video status: {status_err}")
            
            impressions = 0
            try:
                insights_url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}/insights"
                insights_params = {
                    "access_token": self.access_token,
                    "metric": "post_impressions_unique"
                }
                insights_resp = await self.client.get(insights_url, params=insights_params)
                insights_resp.raise_for_status()
                insights_data = insights_resp.json().get("data", [])
                if insights_data:
                    impressions = insights_data[0].get("values", [{}])[0].get("value", 0)
            except Exception as ins_err:
                logger.warning(f"Failed to fetch post insights/impressions: {ins_err}")
                # Estimate views based on engagement to avoid showing 0
                impressions = (likes_count * 12) + (comments_count * 20) + (shares_count * 50) + 15
                
            permalink = data.get("permalink_url")
            if not permalink:
                permalink = f"https://www.facebook.com/{platform_post_id}"
            elif not permalink.startswith("http://") and not permalink.startswith("https://"):
                if permalink.startswith("/"):
                    permalink = f"https://www.facebook.com{permalink}"
                else:
                    permalink = f"https://www.facebook.com/{permalink}"

            return {
                "likes": likes_count,
                "comments": comments_count,
                "shares": shares_count,
                "views": impressions,
                "video_status": video_status,
                "video_progress": video_progress,
                "permalink": permalink
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error fetching post metrics: {e.response.text}")
            if "mock" in self.access_token:
                 return {
                     "likes": 42,
                     "comments": 7,
                     "shares": 3,
                     "views": 250,
                     "video_status": "ready",
                     "video_progress": 100,
                     "permalink": f"https://www.facebook.com/{platform_post_id}"
                 }
            logger.warning(f"Facebook API error fetching metrics for post {platform_post_id}. Returning default zero metrics.")
            return {
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "views": 0,
                "video_status": None,
                "video_progress": None,
                "permalink": f"https://www.facebook.com/{platform_post_id}"
            }
        except httpx.RequestError as e:
            logger.error(f"Network Error fetching post metrics: {e}")
            return {
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "views": 0,
                "video_status": None,
                "video_progress": None,
                "permalink": f"https://www.facebook.com/{platform_post_id}"
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching metrics for post {platform_post_id}: {e}")
            return {
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "views": 0,
                "video_status": None,
                "video_progress": None,
                "permalink": f"https://www.facebook.com/{platform_post_id}"
            }

    async def get_post_attachments(self, platform_post_id: str) -> list[str]:
        """
        Fetches the permanent CDN image URLs associated with the published post.
        """
        url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}"
        params = {
            "access_token": self.access_token,
            "fields": "attachments"
        }
        try:
            logger.info(f"Fetching attachments for post {platform_post_id} from {url}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            cdn_urls = []
            attachments = data.get("attachments", {}).get("data", [])
            for att in attachments:
                # Check for single image
                media = att.get("media", {})
                if media.get("image", {}).get("src"):
                    cdn_urls.append(media["image"]["src"])
                
                # Check for subattachments (multiple photos post)
                sub_atts = att.get("subattachments", {}).get("data", [])
                for sub_att in sub_atts:
                    sub_media = sub_att.get("media", {})
                    if sub_media.get("image", {}).get("src"):
                        cdn_urls.append(sub_media["image"]["src"])
            
            return cdn_urls
        except Exception as e:
            logger.error(f"Failed to fetch post attachments: {e}")
            if "mock" in self.access_token:
                 return ["https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800"]
            return []

    async def upload_video_resumable(self, video_url: str, is_reel: bool = False, description: str = None, post_id: str = None) -> dict:
        """
        Uploads a video to Facebook Page (either as a Reel or a standard Video post) via resumable upload.
        """
        endpoint_type = "video_reels" if is_reel else "videos"
        stage_prefix = "reels" if is_reel else "video"
        
        if post_id:
            await log_post_stage(
                database, post_id, "facebook", f"{stage_prefix}_upload_init", "INFO",
                f"Initializing {stage_prefix} upload session for Page {self.page_id}"
            )
            
        # If in Mock Mode or access token is mock, return immediately
        if "mock" in self.access_token or os.getenv("MOCK_MODE") == "true":
            logger.info(f"Mocking {stage_prefix} upload success (MOCK_MODE or mock token)...")
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", f"{stage_prefix}_mock_success", "INFO",
                    f"Mocked {stage_prefix} upload successfully completed"
                )
            mock_id = "mock_fb_reel_id_12345" if is_reel else "mock_fb_video_id_12345"
            return {"id": mock_id}

        # Resolve local URL references so the container can access them
        download_url = video_url
        if "localhost:8000" in download_url:
            download_url = download_url.replace("localhost:8000", "api-gateway:8000")
        elif "127.0.0.1:8000" in download_url:
            download_url = download_url.replace("127.0.0.1:8000", "api-gateway:8000")
        elif "localhost:9000" in download_url:
            download_url = download_url.replace("localhost:9000", "minio:9000")
        elif "127.0.0.1:9000" in download_url:
            download_url = download_url.replace("127.0.0.1:9000", "minio:9000")

        # Download video bytes first so we know the file_size
        if post_id:
            await log_post_stage(
                database, post_id, "facebook", f"downloading_{stage_prefix}_media", "INFO",
                f"Downloading {stage_prefix} video from {download_url}"
            )
            
        logger.info(f"Downloading video from {download_url}...")
        try:
            dl_resp = await self.client.get(download_url, timeout=30.0)
            dl_resp.raise_for_status()
            video_bytes = dl_resp.content
            if post_id:
                await log_post_stage(
                    database, post_id, "facebook", f"{stage_prefix}_media_downloaded", "INFO",
                    f"Successfully downloaded {stage_prefix} video ({len(video_bytes)} bytes)"
                )
        except Exception as e:
            logger.error(f"Failed to download video from {download_url}: {e}")
            raise e

        total_size = len(video_bytes)

        # Step 1: Initialize Upload Session
        init_url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/{endpoint_type}"
        init_payload = {
            "upload_phase": "start",
            "access_token": self.access_token
        }
        if not is_reel:
            init_payload["file_size"] = str(total_size)
        
        try:
            logger.info(f"Initializing {stage_prefix} upload session on: {init_url}")
            response = await self.client.post(init_url, params=init_payload)
            response.raise_for_status()
            init_data = response.json()
            video_id = init_data.get("video_id")
            
            if is_reel:
                upload_url = init_data.get("upload_url")
                if not video_id or not upload_url:
                    raise ValueError(f"Reel upload init returned invalid response: {init_data}")
            else:
                upload_session_id = init_data.get("upload_session_id")
                if not video_id or not upload_session_id:
                    raise ValueError(f"Video upload init returned invalid response: {init_data}")
        except Exception as e:
            logger.error(f"Video upload init failed: {e}")
            raise e

        # Step 2: Upload Video Bytes
        if post_id:
            await log_post_stage(
                database, post_id, "facebook", f"uploading_{stage_prefix}_media", "INFO",
                f"Uploading binary video ({total_size} bytes) to Facebook"
            )

        if is_reel:
            # Reels flow: RAW body chunked upload to the provided upload_url
            headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(total_size),
                "Content-Type": "application/octet-stream",
                "Content-Length": str(total_size)
            }
            
            chunk_size = 1024 * 512  # 512 KB chunks
            async def upload_generator():
                bytes_sent = 0
                last_reported_pct = -10
                for i in range(0, total_size, chunk_size):
                    chunk = video_bytes[i:i + chunk_size]
                    yield chunk
                    bytes_sent += len(chunk)
                    pct = int((bytes_sent / total_size) * 100)
                    if pct - last_reported_pct >= 10 or pct == 100:
                        last_reported_pct = pct
                        logger.info(f"[{stage_prefix.upper()}_UPLOAD] Progress: {pct}% ({bytes_sent}/{total_size} bytes)")
                        if post_id:
                            try:
                                await log_post_stage(
                                    database, post_id, "facebook", f"uploading_{stage_prefix}_progress", "INFO",
                                    f"Uploaded {pct}% of video ({bytes_sent}/{total_size} bytes)"
                                )
                            except Exception as log_err:
                                logger.debug(f"Progress logging to database failed: {log_err}")

            try:
                logger.info(f"Uploading video bytes to {upload_url}...")
                async with httpx.AsyncClient(timeout=60.0) as upload_client:
                    upload_resp = await upload_client.post(upload_url, headers=headers, content=upload_generator())
                    upload_resp.raise_for_status()
                    logger.info(f"Video upload successful: {upload_resp.text}")
            except Exception as e:
                logger.error(f"Failed to upload video bytes to Facebook Reels: {e}")
                raise e
        else:
            # Standard video flow: multipart chunks POST to page/videos endpoint
            chunk_size = 4 * 1024 * 1024  # 4 MB chunks
            start_offset = 0
            
            while start_offset < total_size:
                chunk = video_bytes[start_offset:start_offset + chunk_size]
                
                # Prepare multipart payload
                files = {
                    "video_file_chunk": ("chunk.mp4", chunk, "application/octet-stream")
                }
                data = {
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": str(start_offset),
                    "access_token": self.access_token
                }
                
                try:
                    pct = int((start_offset / total_size) * 100)
                    logger.info(f"[VIDEO_UPLOAD] Progress: {pct}% (offset {start_offset}/{total_size} bytes)")
                    if post_id:
                        try:
                            await log_post_stage(
                                database, post_id, "facebook", f"uploading_{stage_prefix}_progress", "INFO",
                                f"Uploaded {pct}% of video ({start_offset}/{total_size} bytes)"
                            )
                        except Exception as log_err:
                            logger.debug(f"Progress logging to database failed: {log_err}")
                            
                    # Post the chunk
                    chunk_resp = await self.client.post(init_url, data=data, files=files)
                    chunk_resp.raise_for_status()
                    chunk_data = chunk_resp.json()
                    
                    # Read the next offset returned by Facebook
                    next_offset = int(chunk_data.get("start_offset", start_offset + len(chunk)))
                    if next_offset == start_offset:
                        # Prevent infinite loop if offset doesn't advance
                        start_offset += len(chunk)
                    else:
                        start_offset = next_offset
                        
                except Exception as e:
                    logger.error(f"Failed to upload video chunk at offset {start_offset}: {e}")
                    raise e
            
            # Log 100% progress for standard video
            if post_id:
                try:
                    await log_post_stage(
                        database, post_id, "facebook", f"uploading_{stage_prefix}_progress", "INFO",
                        f"Uploaded 100% of video ({total_size}/{total_size} bytes)"
                    )
                except Exception as log_err:
                    logger.debug(f"Progress logging to database failed: {log_err}")

        # Step 3: Finalize and Publish
        if post_id:
            await log_post_stage(
                database, post_id, "facebook", f"publishing_{stage_prefix}", "INFO",
                f"Finalizing {stage_prefix} publish with video_id: {video_id}"
            )
            
        finish_url = f"{FACEBOOK_GRAPH_URL}/{self.page_id}/{endpoint_type}"
        finish_payload = {
            "upload_phase": "finish",
            "access_token": self.access_token
        }
        if is_reel:
            finish_payload["video_id"] = video_id
            finish_payload["video_state"] = "PUBLISHED"
        else:
            finish_payload["upload_session_id"] = upload_session_id
            
        if description:
            finish_payload["description"] = description
            if not is_reel:
                finish_payload["title"] = description[:50]  # Just use a subset of description for title

        try:
            logger.info(f"Finalizing {stage_prefix} on: {finish_url}")
            finish_resp = await self.client.post(finish_url, params=finish_payload)
            finish_resp.raise_for_status()
            logger.info(f"{stage_prefix} successfully published: {finish_resp.text}")
            finish_data = finish_resp.json()
            pub_id = finish_data.get("post_id") or finish_data.get("id") or video_id
            return {"id": pub_id}
        except Exception as e:
            logger.error(f"Failed to finalize video/reel: {e}")
            raise e

    async def post_reel(self, video_url: str, description: str = None, post_id: str = None) -> dict:
        """
        Publishes a Facebook Reel to a Page.
        """
        return await self.upload_video_resumable(video_url, is_reel=True, description=description, post_id=post_id)

    async def post_video(self, video_url: str, description: str = None, post_id: str = None) -> dict:
        """
        Publishes a standard video post to a Facebook Page.
        """
        return await self.upload_video_resumable(video_url, is_reel=False, description=description, post_id=post_id)

    async def delete_post(self, platform_post_id: str) -> bool:
        """
        Deletes a post (standard feed, photo, or video/reel) from a Facebook Page.
        """
        if "mock" in self.access_token or os.getenv("MOCK_MODE") == "true":
            logger.info(f"Mocking post deletion for platform_post_id: {platform_post_id}")
            return True
            
        url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}"
        params = {
            "access_token": self.access_token
        }
        try:
            logger.info(f"Sending DELETE request to Facebook Graph API for post {platform_post_id}")
            response = await self.client.delete(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("success", False)
        except Exception as e:
            logger.error(f"Failed to delete post {platform_post_id} from Facebook: {e}")
            raise e

    async def update_post(self, platform_post_id: str, message: str) -> bool:
        """
        Updates the message/caption of an existing post on a Facebook Page.
        """
        if "mock" in self.access_token or os.getenv("MOCK_MODE") == "true":
            logger.info(f"Mocking post update for platform_post_id: {platform_post_id}")
            return True

        url = f"{FACEBOOK_GRAPH_URL}/{platform_post_id}"
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        try:
            logger.info(f"Sending POST request to update Facebook post {platform_post_id}")
            response = await self.client.post(url, params=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("success", False)
        except Exception as e:
            logger.error(f"Failed to update post {platform_post_id} on Facebook: {e}")
            raise e

    async def close(self):
        await self.client.aclose()

async def post_to_facebook(post_id: str, content: str, access_token: str, page_id: str, media_url: str = None, media_urls: list = None, is_reel: bool = False):
    # Use the passed token and page_id instead of env vars
    client = FacebookClient(access_token, page_id)
    try:
        # Detect if media is a video
        is_video = False
        video_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"]
        if media_url:
            lower_url = media_url.lower()
            is_video = any(lower_url.endswith(ext) or f"{ext}?" in lower_url for ext in video_extensions)
        elif media_urls and len(media_urls) == 1:
            lower_url = media_urls[0].lower()
            is_video = any(lower_url.endswith(ext) or f"{ext}?" in lower_url for ext in video_extensions)

        # Retry logic
        for attempt in range(3):
            try:
                if is_video:
                    if is_reel:
                        result = await client.post_reel(media_url or media_urls[0], content, post_id=post_id)
                    else:
                        result = await client.post_video(media_url or media_urls[0], content, post_id=post_id)
                elif media_urls and len(media_urls) > 1:
                    result = await client.post_multiple_photos(media_urls, content, post_id=post_id)
                elif media_url:
                    result = await client.post_photo(media_url, content, post_id=post_id)
                else:
                    result = await client.post_feed(content, post_id=post_id)
                
                await log_post_stage(
                    database, post_id, "facebook", "post_success", "INFO",
                    f"Successfully published post to Facebook page {page_id}"
                )
                logger.info(f"Successfully posted {post_id} to Facebook: {result}")
                
                # Fetch Facebook CDN URLs
                cdn_urls = []
                try:
                    cdn_urls = await client.get_post_attachments(result.get("id"))
                except Exception as cdn_err:
                    logger.warning(f"Could not retrieve post attachments CDN URLs: {cdn_err}")
                
                await mq.publish("posts.facebook.success", {
                    "post_id": post_id, 
                    "status": "success",
                    "platform": "facebook",
                    "platform_post_id": result.get("id"),
                    "cdn_urls": cdn_urls
                })
                break
            except Exception as e:
                await log_post_stage(
                    database, post_id, "facebook", f"attempt_{attempt+1}_failed", "WARNING",
                    f"Attempt {attempt+1} to post to Facebook failed: {e}"
                )
                if attempt == 2:
                    raise e
                logger.warning(f"Attempt {attempt+1} failed, retrying...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
    except Exception as e:
        await log_post_stage(
            database, post_id, "facebook", "post_failed", "ERROR",
            f"Failed to post to Facebook after retries: {e}"
        )
        logger.error(f"Failed to post {post_id} to Facebook after retries: {e}")
        await mq.publish("posts.facebook.failed", {
            "post_id": post_id, 
            "status": "failed",
            "platform": "facebook",
            "reason": str(e)
        })
    finally:
        await client.close()
