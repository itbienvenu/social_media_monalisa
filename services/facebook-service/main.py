import asyncio
import logging
from services.facebook_service.logic import post_to_facebook
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facebook-service")

mq = MessageQueue("facebook-service")

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    await post_to_facebook(post_id, content)

async def main():
    logger.info("Starting Facebook Service...")
    # Mock subscription
    await mq.subscribe("posts.facebook", handle_post_event)
    
    # Keep running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
