"""TTL cache for GitHub results, stored as plain Redis keys.

Every write also keeps a long-lived stale copy. If GitHub is down or
rate-limited, callers can fall back to it (journey G7).
"""

import json
from typing import Any

import redis.asyncio as aioredis

FRESH = "cache:"
STALE = "stale:"


class Cache:
    def __init__(self, redis: aioredis.Redis, stale_ttl: int):
        self.redis = redis
        self.stale_ttl = stale_ttl

    async def get(self, key: str) -> Any | None:
        raw = await self.redis.get(FRESH + key)
        return None if raw is None else json.loads(raw)

    async def get_stale(self, key: str) -> Any | None:
        raw = await self.redis.get(STALE + key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        raw = json.dumps(value)
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.set(FRESH + key, raw, ex=ttl)
            pipe.set(STALE + key, raw, ex=self.stale_ttl)
            await pipe.execute()
