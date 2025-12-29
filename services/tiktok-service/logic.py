import asyncio
import logging
from libs.common.messaging import MessageQueue

logger = logging.getLogger("tiktok-service")
mq = MessageQueue("tiktok-service")

async def post_to_tiktok(post_id: str, content: str):
    logger.info(f"Posting to TikTok: {content}")
    await asyncio.sleep(2)
    logger.info(f"Successfully posted {post_id} to TikTok")
    await mq.publish("posts.tiktok.success", {"post_id": post_id, "status": "success"})
