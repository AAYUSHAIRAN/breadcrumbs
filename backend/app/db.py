"""Connections to FalkorDB.

One instance serves two purposes: the graph (user progress) and plain Redis
keys (the TTL cache for GitHub results).
"""

from functools import lru_cache

import redis.asyncio as aioredis
from falkordb.asyncio import FalkorDB

from app.config import get_settings


@lru_cache
def get_falkor() -> FalkorDB:
    s = get_settings()
    return FalkorDB(host=s.falkordb_host, port=s.falkordb_port, password=s.falkordb_password or None)


def get_graph():
    return get_falkor().select_graph(get_settings().graph_name)


@lru_cache
def get_redis() -> aioredis.Redis:
    s = get_settings()
    return aioredis.Redis(
        host=s.falkordb_host,
        port=s.falkordb_port,
        password=s.falkordb_password or None,
        decode_responses=True,
    )
