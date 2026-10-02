import json
from typing import Any

from redis.asyncio import Redis


class JsonCache:
    """Кэш ответов поставщиков в Redis: повторная проверка того же ИНН не стоит денег."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: Any) -> None:
        await self._redis.set(key, json.dumps(value, ensure_ascii=False), ex=self._ttl)
