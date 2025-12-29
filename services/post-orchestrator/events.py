from libs.common.messaging import MessageQueue
import uuid
from libs.common.serializers import Platform

mq = MessageQueue("post-orchestrator")

async def publish_post_event(post_id: uuid.UUID, platform: Platform, content: str, media_key: str = None):
    event = {
        "post_id": str(post_id),
        "platform": platform,
        "content": content,
        "media_key": media_key
    }
    await mq.publish(f"posts.{platform}", event)
