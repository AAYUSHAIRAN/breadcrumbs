"""B1: candidates → checks → ranked issue cards."""

import asyncio
from datetime import UTC, datetime

from app.contracts import Fingerprint, IssueCard
from app.discovery import checks, rank
from app.discovery.search import find_candidates
from app.github import GitHub
from app.registry import Registry

CHECK_TOP = 25  # check only the most promising candidates: each check costs API calls
SHOW = 10


async def find_matches(
    github: GitHub, registry: Registry, fp: Fingerprint, seen: set[str], now: datetime | None = None
) -> list[IssueCard]:
    now = now or datetime.now(UTC)
    candidates = await find_candidates(github, registry, fp, seen, now)
    candidates = sorted(candidates, key=lambda c: rank.prerank(c, fp, now), reverse=True)[:CHECK_TOP]
    if not candidates:
        return []

    stats, claims = await asyncio.gather(
        checks.fetch_repo_stats(github, sorted({c.repo for c in candidates}), now),
        checks.fetch_claims(github, candidates, now),
    )
    cards = [rank.score(c, fp, stats.get(c.repo), claims[c.id], now) for c in candidates]
    return diversify(sorted(cards, key=lambda card: card.fit, reverse=True))[:SHOW]


def diversify(cards: list[IssueCard]) -> list[IssueCard]:
    """Best issue from each repo first, then second-best ones, each group by fit."""
    firsts, rest, repos = [], [], set()
    for card in cards:
        (rest if card.repo in repos else firsts).append(card)
        repos.add(card.repo)
    return firsts + rest
