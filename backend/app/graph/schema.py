"""Graph indexes. Safe to run repeatedly: existing indexes are skipped."""

import logging

from app.db import get_graph

log = logging.getLogger(__name__)

INDEXES = [
    # Progress
    "CREATE INDEX FOR (u:User) ON (u.login)",
    "CREATE INDEX FOR (t:Tech) ON (t.name)",
    "CREATE INDEX FOR (r:Repo) ON (r.name)",
    "CREATE INDEX FOR (i:Issue) ON (i.id)",
    "CREATE INDEX FOR (a:Attempt) ON (a.id)",
    "CREATE INDEX FOR (e:Event) ON (e.key)",
    # Code slice (Layer 2)
    "CREATE INDEX FOR (f:File) ON (f.id)",
    "CREATE INDEX FOR (fn:Function) ON (fn.id)",
    "CALL db.idx.fulltext.createNodeIndex('Function', 'name')",
]


async def ensure_schema() -> None:
    graph = get_graph()
    for statement in INDEXES:
        try:
            await graph.query(statement)
        except Exception as e:  # FalkorDB raises a plain ResponseError for "already indexed"
            if "already" not in str(e).lower():
                raise
    log.info("graph schema ready")
