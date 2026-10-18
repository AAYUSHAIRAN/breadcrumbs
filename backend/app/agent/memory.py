"""The agent's memory, in the graph (Track 2: context that survives sessions).

(User)─HAD─▶(Session)─HAS─▶(Message {role, text, seq, at})
(User)─REMEMBERS─▶(Memory {text, kind, at})        facts the agent learned about the user
(Session)─DECIDED {action, reason, at}─▶(Issue)     every action, with why
"""

import uuid
from datetime import UTC, datetime

from app.graph.progress import _rows


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


async def ensure_session(login: str, session_id: str | None) -> str:
    sid = session_id or uuid.uuid4().hex[:12]
    await _rows(
        """
        MATCH (u:User {login: $login})
        MERGE (s:Session {id: $sid})
        ON CREATE SET s.started_at = $now
        MERGE (u)-[:HAD]->(s)
        """,
        {"login": login, "sid": sid, "now": _now()},
    )
    return sid


async def add_message(sid: str, role: str, text: str) -> None:
    await _rows(
        """
        MATCH (s:Session {id: $sid})
        OPTIONAL MATCH (s)-[:HAS]->(m:Message)
        WITH s, count(m) AS n
        CREATE (s)-[:HAS]->(:Message {role: $role, text: $text, seq: n, at: $now})
        """,
        {"sid": sid, "role": role, "text": text, "now": _now()},
    )


async def history(sid: str, limit: int = 20) -> list[dict]:
    rows = await _rows(
        "MATCH (:Session {id: $sid})-[:HAS]->(m:Message) RETURN m.role, m.text ORDER BY m.seq DESC LIMIT $limit",
        {"sid": sid, "limit": limit},
    )
    return [{"role": r, "content": t} for r, t in reversed(rows)]


async def remember(login: str, text: str, kind: str, sid: str) -> None:
    await _rows(
        """
        MATCH (u:User {login: $login})
        CREATE (u)-[:REMEMBERS]->(:Memory {id: $id, text: $text, kind: $kind, at: $now, session: $sid})
        """,
        {"login": login, "id": uuid.uuid4().hex[:10], "text": text, "kind": kind, "now": _now(), "sid": sid},
    )


async def forget(login: str, memory_id: str) -> None:
    await _rows("MATCH (:User {login: $login})-[:REMEMBERS]->(m:Memory {id: $id}) DETACH DELETE m", {"login": login, "id": memory_id})


async def memories(login: str, limit: int = 20) -> list[dict]:
    rows = await _rows(
        "MATCH (:User {login: $login})-[:REMEMBERS]->(m:Memory) RETURN m {.*} ORDER BY m.at DESC LIMIT $limit",
        {"login": login, "limit": limit},
    )
    return [r[0] for r in rows]


async def record_decision(sid: str, issue_id: str, action: str, reason: str) -> None:
    await _rows(
        """
        MATCH (s:Session {id: $sid})
        MERGE (i:Issue {id: $issue})
        CREATE (s)-[:DECIDED {action: $action, reason: $reason, at: $now}]->(i)
        """,
        {"sid": sid, "issue": issue_id, "action": action, "reason": reason, "now": _now()},
    )


async def decisions(login: str, limit: int = 10) -> list[dict]:
    rows = await _rows(
        """
        MATCH (:User {login: $login})-[:HAD]->(:Session)-[d:DECIDED]->(i:Issue)
        RETURN i.id, i.title, d.action, d.reason, d.at ORDER BY d.at DESC LIMIT $limit
        """,
        {"login": login, "limit": limit},
    )
    return [{"issue_id": a, "title": b, "action": c, "reason": d, "at": e} for a, b, c, d, e in rows]


async def previous_sessions(login: str, current: str, limit: int = 3) -> list[dict]:
    """Last few messages of earlier sessions, so the agent can say 'last time…'."""
    rows = await _rows(
        """
        MATCH (:User {login: $login})-[:HAD]->(s:Session)-[:HAS]->(m:Message)
        WHERE s.id <> $current
        WITH s, m ORDER BY m.seq DESC
        WITH s, collect({role: m.role, text: m.text})[..4] AS recent
        RETURN s.id, s.started_at, recent ORDER BY s.started_at DESC LIMIT $limit
        """,
        {"login": login, "current": current, "limit": limit},
    )
    return [{"session": a, "at": b, "recent": list(reversed(c))} for a, b, c in rows]
