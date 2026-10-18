import os

os.environ["GRAPH_NAME"] = "breadcrumbs_test"
os.environ["MODE"] = "mock"

import pytest

from app.db import get_falkor, get_graph
from app.graph.schema import ensure_schema


@pytest.fixture
async def graph():
    """A fresh test graph per test."""
    g = get_graph()
    if g.name in await get_falkor().list_graphs():
        await g.delete()
    await ensure_schema()
    yield g
