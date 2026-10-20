"""Connections to FalkorDB.

One instance serves two purposes: the graph (user progress) and plain Redis
keys (the TTL cache for GitHub results).
"""

from functools import lru_cache

import redis.asyncio as aioredis
from falkordb.asyncio import FalkorDB
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError

from app.config import get_settings


def _connection_options() -> dict:
    """Survive connections a proxy (e.g. Railway's TCP proxy) closes while they sit idle in the pool.

    - health_check_interval: PING a connection that has been idle this long before reusing it.
    - retry + retry_on_error: on a dropped connection, reconnect and run the command again.
      RuntimeError is what uvloop raises when writing to a transport that is already closed,
      which the client doesn't treat as a connection error by default.
    """
    s = get_settings()
    return {
        "host": s.falkordb_host,
        "port": s.falkordb_port,
        "password": s.falkordb_password or None,
        "socket_keepalive": True,
        "socket_connect_timeout": 10,
        "health_check_interval": 15,
        "retry": Retry(ExponentialBackoff(cap=1, base=0.1), retries=3),
        "retry_on_error": [ConnectionError, TimeoutError, RuntimeError],
    }


@lru_cache
def get_falkor() -> FalkorDB:
    # FalkorDB also builds a *sync* Redis client from these options (to detect cluster mode),
    # which can't take the async Retry object. Without it, retry_on_error still makes the
    # client reconnect and retry once.
    options = _connection_options()
    options.pop("retry")
    return FalkorDB(**options)


def get_graph():
    return get_falkor().select_graph(get_settings().graph_name)


@lru_cache
def get_redis() -> aioredis.Redis:
    return aioredis.Redis(**_connection_options(), decode_responses=True)
