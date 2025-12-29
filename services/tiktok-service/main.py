import asyncio
import logging
from services.tiktok_service.logic import post_to_tiktok
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-service")

mq = MessageQueue("tiktok-service")

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    await post_to_tiktok(post_id, content)

async def main():
    logger.info("Starting TikTok Service...")
    await mq.subscribe("posts.tiktok", handle_post_event)
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
