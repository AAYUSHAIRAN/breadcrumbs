"""Progress repository: everything we remember about a user, in the graph.

Times are stored as epoch seconds so Cypher can compare them directly.
Events are append-only; syncing the same GitHub activity twice is a no-op
because each event's `key` includes its GitHub ID.
"""

import uuid
from datetime import UTC, datetime

from app.contracts import Attempt, Event, Fingerprint, IssueCard, Preferences, Skill
from app.db import get_graph
from app.graph.status import next_status


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


def attempt_id(login: str, issue_id: str) -> str:
    return f"{login}:{issue_id}"


def event_key(attempt: str, event: Event) -> str:
    return f"{attempt}:{event.type}:{event.gh_id or uuid.uuid4().hex}"


async def _rows(query: str, params: dict | None = None) -> list[list]:
    result = await get_graph().query(query, params or {})
    return result.result_set


# --- Users and skills ----------------------------------------------------------


async def upsert_user(fp: Fingerprint) -> None:
    """Save a fingerprint. Inferred skills are replaced; manual and learned ones are kept."""
    await _rows(
        """
        MERGE (u:User {login: $login})
        SET u.name = $name, u.avatar_url = $avatar_url, u.level = $level,
            u.merged_prs = $merged_prs, u.dependencies = $dependencies, u.synced_at = $now
        WITH u
        OPTIONAL MATCH (u)-[k:KNOWS {source: 'inferred'}]->(:Tech)
        DELETE k
        """,
        fp.model_dump(exclude={"skills"}) | {"now": _ts(datetime.now(UTC))},
    )
    skills = [s.model_dump() for s in fp.skills if s.source == "inferred"]
    if skills:
        await _rows(
            """
            MATCH (u:User {login: $login})
            UNWIND $skills AS s
            MERGE (t:Tech {name: s.tech})
            SET t.kind = coalesce(t.kind, s.kind)
            MERGE (u)-[k:KNOWS]->(t)
            ON CREATE SET k.level = s.level, k.source = 'inferred'
            """,
            {"login": fp.login, "skills": skills},
        )


async def get_user(login: str) -> Fingerprint | None:
    rows = await _rows(
        """
        MATCH (u:User {login: $login})
        OPTIONAL MATCH (u)-[k:KNOWS]->(t:Tech)
        RETURN u {.*}, collect({tech: t.name, kind: t.kind, level: k.level, source: k.source})
        """,
        {"login": login},
    )
    if not rows:
        return None
    user, skills = rows[0]
    return Fingerprint(
        login=user["login"],
        name=user.get("name"),
        avatar_url=user.get("avatar_url"),
        level=user["level"],
        merged_prs=user.get("merged_prs", 0),
        dependencies=user.get("dependencies", []),
        preferences=Preferences(
            languages=user.get("pref_languages", []),
            difficulty=user.get("pref_difficulty", "auto"),
            hours_per_week=user.get("pref_hours", 3),
        ),
        skills=sorted((Skill(**s) for s in skills if s["tech"] is not None), key=lambda s: s.level, reverse=True),
    )


async def set_preferences(login: str, prefs: Preferences) -> None:
    await _rows(
        """
        MATCH (u:User {login: $login})
        SET u.pref_languages = $languages, u.pref_difficulty = $difficulty, u.pref_hours = $hours
        """,
        {"login": login, "languages": prefs.languages, "difficulty": prefs.difficulty, "hours": prefs.hours_per_week},
    )


async def learn(login: str, techs: dict[str, str], boost: float = 0.1) -> None:
    """After a merge (F1): record what was learned and raise those skill levels.

    `techs` maps tech name → kind, e.g. {"jest": "library"}.
    """
    await _rows(
        """
        MATCH (u:User {login: $login})
        UNWIND keys($techs) AS name
        MERGE (t:Tech {name: name}) ON CREATE SET t.kind = $techs[name]
        MERGE (u)-[l:LEARNED]->(t) ON CREATE SET l.at = $now
        MERGE (u)-[k:KNOWS]->(t) ON CREATE SET k.level = 0, k.source = 'learned'
        SET k.level = CASE WHEN k.level + $boost > 1 THEN 1.0 ELSE k.level + $boost END
        """,
        {"login": login, "techs": techs, "boost": boost, "now": _ts(datetime.now(UTC))},
    )


# --- Shown and skipped ------------------------------------------------------------


async def record_shown(login: str, cards: list[IssueCard]) -> None:
    """Our side of the progress: which issues we recommended, when, and how they scored."""
    if not cards:
        return
    await _rows(
        """
        MATCH (u:User {login: $login})
        UNWIND $cards AS c
        MERGE (r:Repo {name: c.repo})
        SET r.stars = c.stars, r.reply_hours = c.reply_hours, r.newcomer_merges_90d = c.newcomers
        MERGE (i:Issue {id: c.id})
        SET i.title = c.title, i.url = c.url, i.difficulty = c.difficulty
        MERGE (i)-[:IN]->(r)
        FOREACH (_ IN CASE WHEN c.tech <> '' THEN [1] ELSE [] END |
            MERGE (t:Tech {name: c.tech})
            MERGE (i)-[:NEEDS]->(t))
        MERGE (u)-[s:SHOWN]->(i)
        ON CREATE SET s.first_at = $now, s.times = 0
        SET s.at = $now, s.times = s.times + 1, s.fit = c.fit
        """,
        {
            "login": login,
            "now": _ts(datetime.now(UTC)),
            "cards": [
                {
                    "id": c.id, "repo": c.repo, "title": c.title, "url": c.url, "fit": c.fit, "tech": c.tech,
                    "difficulty": c.difficulty, "stars": c.repo_stars, "reply_hours": c.maintainer_reply_hours,
                    "newcomers": c.newcomer_merges_90d,
                }
                for c in cards
            ],
        },
    )



async def save_issue(login: str, card: IssueCard) -> None:
    """B7: bookmark an issue. The card is stored on the edge so the saved list needs no GitHub calls."""
    await record_shown(login, [card])
    await _rows(
        """
        MATCH (u:User {login: $login}), (i:Issue {id: $id})
        MERGE (u)-[s:SAVED]->(i)
        SET s.at = $now, s.card = $card
        """,
        {"login": login, "id": card.id, "now": _ts(datetime.now(UTC)), "card": card.model_dump_json()},
    )


async def unsave_issue(login: str, issue_id: str) -> None:
    await _rows("MATCH (:User {login: $login})-[s:SAVED]->(:Issue {id: $id}) DELETE s", {"login": login, "id": issue_id})


async def saved_issues(login: str) -> list[IssueCard]:
    rows = await _rows(
        "MATCH (:User {login: $login})-[s:SAVED]->(:Issue) RETURN s.card ORDER BY s.at DESC", {"login": login}
    )
    return [IssueCard.model_validate_json(r[0]).model_copy(update={"saved": True}) for r in rows]


async def skip_issue(login: str, issue_id: str, reason: str) -> None:
    await _rows(
        """
        MATCH (u:User {login: $login})
        MERGE (i:Issue {id: $issue_id})
        MERGE (u)-[s:SKIPPED]->(i)
        SET s.reason = $reason, s.at = $now
        """,
        {"login": login, "issue_id": issue_id, "reason": reason, "now": _ts(datetime.now(UTC))},
    )


async def seen_issue_ids(login: str) -> set[str]:
    """Issues to leave out of new matches: skipped or already attempted."""
    rows = await _rows(
        """
        MATCH (u:User {login: $login})
        OPTIONAL MATCH (u)-[:SKIPPED]->(s:Issue)
        OPTIONAL MATCH (u)-[:WORKING_ON]->(:Attempt)-[:FOR]->(a:Issue)
        RETURN collect(DISTINCT s.id) + collect(DISTINCT a.id)
        """,
        {"login": login},
    )
    return set(rows[0][0]) if rows else set()


# --- Attempts and events -----------------------------------------------------


async def start_attempt(login: str, issue_id: str, title: str, url: str, repo: str) -> Attempt:
    """C1: the user picks an issue. Picking the same issue again returns the existing attempt."""
    aid = attempt_id(login, issue_id)
    now = _ts(datetime.now(UTC))
    await _rows(
        """
        MATCH (u:User {login: $login})
        MERGE (r:Repo {name: $repo})
        MERGE (i:Issue {id: $issue_id})
        SET i.title = $title, i.url = $url
        MERGE (i)-[:IN]->(r)
        MERGE (a:Attempt {id: $aid})
        ON CREATE SET a.status = 'selected', a.started_at = $now, a.last_activity_at = $now
        MERGE (u)-[:WORKING_ON]->(a)
        MERGE (a)-[:FOR]->(i)
        """,
        {"login": login, "repo": repo, "issue_id": issue_id, "title": title, "url": url, "aid": aid, "now": now},
    )
    await append_events(aid, [Event(type="selected", at=_dt(now), gh_id="selected", summary="Picked this issue")])
    attempt = await get_attempt(aid)
    assert attempt is not None
    return attempt


async def append_events(aid: str, events: list[Event]) -> list[Event]:
    """Add new events in time order, skipping ones already recorded. Returns the new ones."""
    rows = await _rows(
        """
        MATCH (a:Attempt {id: $aid})
        OPTIONAL MATCH (a)-[:HAS_EVENT]->(e:Event)
        RETURN a.status, collect(e.key)
        """,
        {"aid": aid},
    )
    if not rows:
        raise KeyError(f"no attempt {aid}")
    status, existing = rows[0][0], set(rows[0][1])

    new: list[tuple[str, Event]] = []
    for event in sorted(events, key=lambda e: e.at):
        key = event_key(aid, event)
        if key not in existing:
            existing.add(key)
            new.append((key, event))
            status = next_status(status, event.type)
    if not new:
        return []

    await _rows(
        """
        MATCH (a:Attempt {id: $aid})
        UNWIND $events AS ev
        CREATE (a)-[:HAS_EVENT]->(:Event {key: ev.key, type: ev.type, at: ev.at,
                                          gh_id: ev.gh_id, url: ev.url, summary: ev.summary})
        WITH a, max(ev.at) AS latest
        SET a.status = $status,
            a.last_activity_at = CASE WHEN latest > a.last_activity_at THEN latest ELSE a.last_activity_at END
        """,
        {
            "aid": aid,
            "status": status,
            "events": [
                {"key": k, "type": e.type, "at": _ts(e.at), "gh_id": e.gh_id, "url": e.url, "summary": e.summary}
                for k, e in new
            ],
        },
    )
    pr_urls = [e.url for _, e in new if e.type == "pr_opened" and e.url]
    if pr_urls:
        await _rows("MATCH (a:Attempt {id: $aid}) SET a.pr_url = $url", {"aid": aid, "url": pr_urls[-1]})
    return [e for _, e in new]


_ATTEMPT_RETURN = """
    OPTIONAL MATCH (a)-[:HAS_EVENT]->(e:Event)
    WITH a, i, e ORDER BY e.at
    RETURN a {.*}, i {.*}, collect(e {.*})
"""


def _to_attempt(row: list) -> Attempt:
    a, i, events = row
    return Attempt(
        id=a["id"],
        issue_id=i["id"],
        issue_title=i.get("title", ""),
        issue_url=i.get("url", ""),
        status=a["status"],
        started_at=_dt(a["started_at"]),
        last_activity_at=_dt(a["last_activity_at"]),
        pr_url=a.get("pr_url"),
        events=[
            Event(type=e["type"], at=_dt(e["at"]), gh_id=e.get("gh_id"), url=e.get("url"), summary=e.get("summary", ""))
            for e in events
        ],
    )


async def get_attempt(aid: str) -> Attempt | None:
    rows = await _rows("MATCH (a:Attempt {id: $aid})-[:FOR]->(i:Issue)" + _ATTEMPT_RETURN, {"aid": aid})
    return _to_attempt(rows[0]) if rows else None


async def list_attempts(login: str) -> list[Attempt]:
    rows = await _rows(
        "MATCH (:User {login: $login})-[:WORKING_ON]->(a:Attempt)-[:FOR]->(i:Issue)" + _ATTEMPT_RETURN,
        {"login": login},
    )
    return sorted((_to_attempt(r) for r in rows), key=lambda a: a.last_activity_at, reverse=True)


async def remove_attempt(login: str, issue_id: str) -> bool:
    """Take an issue off the user's trail: delete the attempt and its timeline.

    The Issue node stays (other users may share it), so it can be recommended again.
    """
    rows = await _rows(
        """
        MATCH (:User {login: $login})-[:WORKING_ON]->(a:Attempt {id: $aid})
        OPTIONAL MATCH (a)-[:HAS_EVENT]->(e:Event)
        WITH a, collect(e) AS events
        FOREACH (e IN events | DETACH DELETE e)
        DETACH DELETE a
        RETURN count(a)
        """,
        {"login": login, "aid": attempt_id(login, issue_id)},
    )
    return bool(rows and rows[0][0])
