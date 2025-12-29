from collections import defaultdict
import asyncio
import json
import logging
import os
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        self.redis = None
        self.pubsub = None
        self._handlers = defaultdict(list)

    async def connect(self):
        if not self.redis:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis.pubsub()
            logger.info(f"[{self.service_name}] Connected to Redis at {self.redis_url}")

    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            logger.info(f"[{self.service_name}] Disconnected from Redis")

    async def publish(self, topic: str, message: dict):
        if not self.redis:
            await self.connect()
        logger.info(f"[{self.service_name}] Publishing to {topic}: {message}")
        await self.redis.publish(topic, json.dumps(message))

    async def subscribe(self, topic: str, handler):
        if not self.redis:
            await self.connect()
        self._handlers[topic].append(handler)
        await self.pubsub.subscribe(topic)
        logger.info(f"[{self.service_name}] Subscribed to {topic}")
        # Note: We rely on the service loop to run listen() separately
        # Or we can spawn a task here.
        # Spawning here is easier for usage compat.
        if len(self._handlers) == 1: # First subscription
             asyncio.create_task(self.start_listening())

    async def start_listening(self):
        if not self.pubsub:
            await self.connect()
        
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    topic = message['channel']
                    try:
                        data = json.loads(message['data'])
                        handlers = self._handlers.get(topic, [])
                        for h in handlers:
                             try:
                                 await h(data)
                             except Exception as e:
                                 logger.error(f"Error handling message on {topic}: {e}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode message on {topic}")
        except Exception as e:
             logger.error(f"Redis listener error: {e}")
             # Reconnect logic would go here
