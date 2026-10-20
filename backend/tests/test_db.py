"""Connections dropped while idle in the pool (e.g. by Railway's TCP proxy) must be replaced, not reused."""

import asyncio

import uvloop

from app import db


def _drop_idle(pool) -> int:
    conns = list(pool._available_connections)
    for conn in conns:
        conn._writer.transport.abort()
    return len(conns)


def test_cache_client_recovers_from_dropped_connection():
    """Runs on uvloop, like uvicorn in production: there, writing to a dropped socket raises RuntimeError."""

    async def scenario():
        r = db.get_redis.__wrapped__()  # a fresh client on this loop, same options as production
        await r.set("bc:test:drop", "1")
        assert _drop_idle(r.connection_pool) > 0
        await asyncio.sleep(0.1)
        value = await r.get("bc:test:drop")
        await r.aclose()
        return value

    assert uvloop.run(scenario()) == "1"


async def test_graph_client_recovers_from_dropped_connection(graph):
    await graph.query("RETURN 1")
    assert _drop_idle(db.get_falkor().connection.connection_pool) > 0
    await asyncio.sleep(0.1)
    assert (await graph.query("RETURN 42")).result_set == [[42]]
