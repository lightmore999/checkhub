import time

from redis.asyncio import Redis


async def hit_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int = 60) -> bool:
    """Фиксированное окно: считаем запросы ключа в текущей минуте.

    Возвращает True, если лимит превышен.
    """
    bucket = int(time.time() // window_seconds)
    redis_key = f"ratelimit:{key}:{bucket}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)
    return count > limit
