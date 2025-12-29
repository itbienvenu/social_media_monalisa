import asyncio
import logging
from libs.common.messaging import MessageQueue

logger = logging.getLogger("linkedin-service")
mq = MessageQueue("linkedin-service")

async def post_to_linkedin(post_id: str, content: str):
    logger.info(f"Posting to LinkedIn: {content}")
    await asyncio.sleep(2)
    logger.info(f"Successfully posted {post_id} to LinkedIn")
    await mq.publish("posts.linkedin.success", {"post_id": post_id, "status": "success"})
