import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

class MessageQueue:
    """
    Mock Message Queue interface.
    In a real implementation, this would connect to RabbitMQ or Kafka.
    """
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.listeners: list[Callable] = []

    async def publish(self, topic: str, message: dict[str, Any]):
        """
        Mock publish. Just logs the event.
        """
        logger.info(f"[{self.service_name}] Published to {topic}: {json.dumps(message)}")

    async def subscribe(self, topic: str, callback: Callable):
        """
        Mock subscribe.
        For now, this won't actually receive messages across processes because we are mocking.
        In a real scenario, this would start a consumer loop.
        """
        logger.info(f"[{self.service_name}] Subscribed to {topic}")
        self.listeners.append((topic, callback))

    # Helper for simulation
    async def simulate_receive(self, topic: str, message: dict[str, Any]):
        for t, callback in self.listeners:
            if t == topic:
                await callback(message)
