import asyncio
import logging
from services.linkedin_service.logic import post_to_linkedin
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin-service")

mq = MessageQueue("linkedin-service")

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    await post_to_linkedin(post_id, content)

async def main():
    logger.info("Starting LinkedIn Service...")
    await mq.subscribe("posts.linkedin", handle_post_event)
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
