import json
import logging
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        self._redis = None
        self._available = True

    async def _get_redis(self):
        if not self._available:
            return None
        if self._redis is None:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable: {e}, notifications disabled")
                self._available = False
                self._redis = None
                return None
        return self._redis

    async def publish(self, channel: str, message: dict):
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.publish(channel, json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")
            self._available = False
            self._redis = None

    async def notify_new_ticket(self, engineer_id: str, ticket_data: dict):
        await self.publish(f"engineer:{engineer_id}:notify", {
            "type": "new_ticket",
            "payload": ticket_data,
        })

    async def notify_urge(self, engineer_id: str, ticket_data: dict):
        await self.publish(f"engineer:{engineer_id}:notify", {
            "type": "urge",
            "payload": ticket_data,
        })

    async def notify_admin_alert(self, alert_type: str, data: dict):
        await self.publish("admin:alert", {
            "type": alert_type,
            "payload": data,
        })

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel.

        Returns a PubSub object. Caller is responsible for:
        - await pubsub.unsubscribe(channel)
        - await pubsub.close()
        """
        r = await self._get_redis()
        if r is None:
            return None
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        return pubsub


notification_service = NotificationService()