from collections import defaultdict
import asyncio
import json
import logging
import os
import aio_pika

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://user:password@rabbitmq:5672/")
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        if not self.connection:
            try:
                self.connection = await aio_pika.connect_robust(
                    self.rabbitmq_url,
                    client_properties={"connection_name": self.service_name}
                )
                self.channel = await self.connection.channel()
                # Declare topic exchange
                self.exchange = await self.channel.declare_exchange(
                    "social_events", aio_pika.ExchangeType.TOPIC
                )
                logger.info(f"[{self.service_name}] Connected to RabbitMQ at {self.rabbitmq_url}")
            except Exception as e:
                logger.error(f"[{self.service_name}] Failed to connect to RabbitMQ: {e}")
                raise e

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
            logger.info(f"[{self.service_name}] Disconnected from RabbitMQ")

    async def publish(self, topic: str, message: dict):
        if not self.exchange:
            await self.connect()
        
        try:
            await self.exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    content_type="application/json"
                ),
                routing_key=topic
            )
            logger.info(f"[{self.service_name}] Published to {topic}: {message}")
        except Exception as e:
            logger.error(f"[{self.service_name}] Failed to publish: {e}")
            raise e

    async def subscribe(self, topic: str, handler):
        if not self.channel:
            await self.connect()
            
        # Declare queue with unique name if not load balancing, or shared for workers.
        # For this pattern, we want durable queues per service-topic pair usually.
        queue_name = f"{self.service_name}.{topic}"
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.bind(self.exchange, routing_key=topic)
        
        logger.info(f"[{self.service_name}] Subscribed to {topic} via queue {queue_name}")

        async def _callback(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    await handler(data)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        await queue.consume(_callback)
