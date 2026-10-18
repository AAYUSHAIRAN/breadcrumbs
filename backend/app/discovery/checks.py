"""Checks on candidate issues (T1.4): is it claimed, and how does the repo treat newcomers?

Repo stats come from the repo's 50 most recently updated merged or closed PRs,
fetched once per repo and cached for 24 hours. Claims come from each issue's
latest comments, fetched in batches.

GitHub's authorAssociation is the author's *current* relationship, so a
newcomer whose PR merged shows as CONTRIBUTOR. "Newcomer" is therefore an
approximation: not a bot, not a maintainer, and only one PR in the sample.
"""

import asyncio
import json
import re
import statistics
from collections import Counter
from datetime import datetime, timedelta

from pydantic import BaseModel

from app.config import get_settings
from app.discovery.search import Candidate
from app.github import GitHub

MAINTAINER = {"OWNER", "MEMBER", "COLLABORATOR"}
BOT_LOGIN = re.compile(r"(\[bot\]|bot)$", re.IGNORECASE)
NEWCOMER_WINDOW = timedelta(days=90)
CLAIM_EXPIRY = timedelta(days=21)  # a claim with no PR after this is fair game
ISSUES_PER_CALL = 15
MAX_PARALLEL = 8

REPO_STATS_QUERY = """
query RepoStats($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    pullRequests(first: 50, states: [MERGED, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        createdAt mergedAt closedAt authorAssociation
        author { __typename login }
        reviews(first: 1) { nodes { createdAt author { __typename login } } }
        comments(first: 3) { nodes { createdAt author { __typename login } } }
      }
    }
  }
}
"""

COMMENT_FIELDS = """
      number
      repository { nameWithOwner }
      comments(last: 10) {
        nodes { createdAt body authorAssociation author { __typename login } }
      }
"""

CLAIM_PHRASES = re.compile(
    r"\b(can|could|may) i (work|take|pick|try|grab|tackle)\b"
    r"|\bi('d| would) (like|love) to (work|take|pick|try|contribute|tackle)\b"
    r"|\bassign (it |this )?(to )?me\b"
    r"|\bi('ll| will) (work|take|pick|try|tackle|handle)\b"
    r"|\b(i'?m|i am) (working|on it|on this|taking)\b"
    r"|\bworking on (this|it)\b"
    r"|\bplease assign\b",
    re.IGNORECASE,
)
GO_AHEAD = re.compile(r"\b(go ahead|assigned|it'?s yours|all yours|sure,? (go|feel free)|feel free)\b", re.IGNORECASE)


class RepoStats(BaseModel):
    repo: str
    reply_hours: float | None  # median time to first non-author, non-bot response
    newcomer_merges_90d: int
    newcomer_merged: int  # in the whole sample, for the merge forecast
    newcomer_closed: int


class Claim(BaseModel):
    claimed: bool
    by: str | None = None
    at: datetime | None = None
    expired: bool = False  # someone asked, but long ago and nothing happened
    acknowledged: bool = False  # a maintainer said go ahead


def _is_bot(author: dict | None) -> bool:
    return not author or author.get("__typename") == "Bot" or bool(BOT_LOGIN.search(author.get("login", "")))


def _login(author: dict | None) -> str | None:
    return author.get("login") if author else None


# --- Pure parsers ---------------------------------------------------------------


def repo_stats(repo: str, data: dict | None, now: datetime) -> RepoStats:
    prs = ((data or {}).get("repository") or {}).get("pullRequests", {}).get("nodes", [])
    humans = [p for p in prs if not _is_bot(p["author"])]
    counts = Counter(_login(p["author"]) for p in humans)

    replies = []
    for pr in humans:
        author = _login(pr["author"])
        responses = [
            datetime.fromisoformat(n["createdAt"])
            for n in pr["reviews"]["nodes"] + pr["comments"]["nodes"]
            if not _is_bot(n["author"]) and _login(n["author"]) != author
        ]
        if responses:
            hours = (min(responses) - datetime.fromisoformat(pr["createdAt"])).total_seconds() / 3600
            replies.append(max(hours, 0))

    newcomers = [p for p in humans if p["authorAssociation"] not in MAINTAINER and counts[_login(p["author"])] == 1]
    merged = [p for p in newcomers if p["mergedAt"]]
    return RepoStats(
        repo=repo,
        reply_hours=round(statistics.median(replies), 1) if replies else None,
        newcomer_merges_90d=sum(datetime.fromisoformat(p["mergedAt"]) >= now - NEWCOMER_WINDOW for p in merged),
        newcomer_merged=len(merged),
        newcomer_closed=len(newcomers) - len(merged),
    )


def claim_status(comments: list[dict], now: datetime) -> Claim:
    """The latest non-maintainer claim, and whether it's still live.

    A claim is live if it's recent, or if a maintainer said go ahead after it.
    """
    latest: Claim | None = None
    for c in sorted(comments, key=lambda c: c["createdAt"]):
        at = datetime.fromisoformat(c["createdAt"])
        if c["authorAssociation"] in MAINTAINER:
            if latest and GO_AHEAD.search(c.get("body") or ""):
                latest.acknowledged = True
            continue
        if not _is_bot(c["author"]) and CLAIM_PHRASES.search(c.get("body") or ""):
            latest = Claim(claimed=True, by=_login(c["author"]), at=at)

    if latest is None:
        return Claim(claimed=False)
    if not latest.acknowledged and now - latest.at > CLAIM_EXPIRY:
        return Claim(claimed=False, by=latest.by, at=latest.at, expired=True)
    return latest


def comments_query(candidates: list[Candidate]) -> str:
    parts = []
    for i, c in enumerate(candidates):
        owner, name = c.repo.split("/", 1)
        parts.append(
            f"  i{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{ issue(number: {c.number}) {{{COMMENT_FIELDS}    }} }}"
        )
    return "query IssueComments {\n" + "\n".join(parts) + "\n}"


def index_comments(responses: list[dict]) -> dict[str, list[dict]]:
    """Issue id → comments, keyed by the data itself (not alias order)."""
    out = {}
    for response in responses:
        for repo in response.values():
            issue = (repo or {}).get("issue")
            if issue:
                out[f"{issue['repository']['nameWithOwner']}#{issue['number']}"] = issue["comments"]["nodes"]
    return out


# --- Fetching -------------------------------------------------------------------------


async def fetch_repo_stats(github: GitHub, repos: list[str], now: datetime) -> dict[str, RepoStats]:
    limit = asyncio.Semaphore(MAX_PARALLEL)
    ttl = get_settings().ttl_repo_stats

    async def one(repo: str) -> RepoStats:
        owner, name = repo.split("/", 1)
        async with limit:
            data = await github.graphql(REPO_STATS_QUERY, {"owner": owner, "name": name}, ttl=ttl)
        return repo_stats(repo, data, now)

    results = await asyncio.gather(*(one(r) for r in repos))
    return {s.repo: s for s in results}


async def fetch_claims(github: GitHub, candidates: list[Candidate], now: datetime) -> dict[str, Claim]:
    batches = [candidates[i : i + ISSUES_PER_CALL] for i in range(0, len(candidates), ISSUES_PER_CALL)]
    responses = await asyncio.gather(*(github.graphql(comments_query(b)) for b in batches))
    comments = index_comments(list(responses))
    return {c.id: claim_status(comments.get(c.id, []), now) for c in candidates}
