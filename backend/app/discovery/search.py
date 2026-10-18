"""Candidate issues for a user (B1, B3): good repos first, then their issues.

Searching issues directly mostly finds tiny personal repos whose owners label
their own to-do lists "help wanted", and issue search can't filter by repo
size or activity. So:

  1. Repo search, one per top language (≤ MAX_LANGUAGES): mid-size, recently
     pushed, not archived, with enough issues labelled for the user's level.
  2. Add the repos behind the user's dependencies (B3).
  3. Batched GraphQL calls fetch open, labelled issues from all of those repos,
     with assignee and linked-PR counts, so unavailable issues can be dropped.

Cost per user: ≤ 3 searches (limit 30/min) + a few GraphQL calls
(REPOS_PER_CALL repos each, in parallel), cached 15 min.
"""

import asyncio
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from app.contracts import Fingerprint, Level
from app.github import GitHub
from app.registry import Registry

MAX_LANGUAGES = 3
MIN_LANGUAGE_LEVEL = 0.15
REPOS_PER_LANGUAGE = 15
MAX_DEPENDENCY_REPOS = 6
ISSUES_PER_REPO = 8
REPOS_PER_CALL = 10  # more than this per GraphQL call hits GitHub's resource limit
PER_REPO = 2  # candidates kept per repo, so one busy repo can't fill the list
MAX_CANDIDATES = 40
FRESH_DAYS = 60
PUSHED_DAYS = 30
STARS = "200..30000"  # big enough to be real, small enough that newcomers get reviewed

LABELS: dict[Level, list[str]] = {
    "beginner": ["good first issue", "good-first-issue", "first-timers-only", "beginner", "easy"],
    "intermediate": ["good first issue", "good-first-issue", "help wanted"],
    "advanced": ["help wanted"],
}
# Repo search qualifier counting labelled issues, per level.
REPO_LABEL_QUALIFIER: dict[Level, str] = {
    "beginner": "good-first-issues:>=3",
    "intermediate": "good-first-issues:>=2",
    "advanced": "help-wanted-issues:>=3",
}

# Build tooling and type stubs: depending on them says little about what you'd fix.
NOISY_DEPENDENCY = re.compile(
    r"^npm:(@types/.*|typescript|eslint.*|prettier|react-scripts|web-vitals|@babel/.*|ts-node|nodemon|rimraf)$"
    r"|^pypi:(pip|setuptools|wheel|black|ruff|flake8|mypy|isort|python-dotenv)$"
)

Source = Literal["language", "dependency"]


class RepoPick(BaseModel):
    repo: str
    source: Source
    matched: str  # the language, or the package it came from


class Candidate(BaseModel):
    id: str  # "owner/repo#number"
    url: str
    repo: str
    repo_stars: int
    number: int
    title: str
    body: str
    labels: list[str]
    comments: int
    created_at: datetime
    updated_at: datetime
    source: Source
    matched: str


# --- Step 1 and 2: which repos ---------------------------------------------------


def _quote(value: str) -> str:
    return f'"{value}"' if re.search(r"[^\w-]", value) else value


def top_languages(fp: Fingerprint) -> list[str]:
    if fp.preferences.languages:  # the user chose (onboarding / profile)
        return fp.preferences.languages[:MAX_LANGUAGES]
    languages = [s.tech for s in fp.skills if s.kind == "language"]
    strong = [s.tech for s in fp.skills if s.kind == "language" and s.level >= MIN_LANGUAGE_LEVEL]
    return (strong or languages[:1])[:MAX_LANGUAGES]


def repo_query(fp: Fingerprint, language: str, today: date) -> str:
    pushed = (today - timedelta(days=PUSHED_DAYS)).isoformat()
    return (
        f"language:{_quote(language)} {REPO_LABEL_QUALIFIER[fp.level]} stars:{STARS} "
        f"pushed:>={pushed} archived:false -user:{fp.login}"
    )


async def language_repos(github: GitHub, fp: Fingerprint, today: date) -> list[RepoPick]:
    async def search(language: str) -> list[RepoPick]:
        data = await github.rest(
            "/search/repositories", {"q": repo_query(fp, language, today), "per_page": REPOS_PER_LANGUAGE}
        )
        return [RepoPick(repo=r["full_name"], source="language", matched=language) for r in data.get("items", [])]

    results = await asyncio.gather(*(search(lang) for lang in top_languages(fp)))
    return [pick for picks in results for pick in picks]


async def dependency_repos(registry: Registry, fp: Fingerprint) -> list[RepoPick]:
    """B3: the GitHub repos behind the user's most-used dependencies."""
    packages = [p for p in fp.dependencies if not NOISY_DEPENDENCY.match(p)][: MAX_DEPENDENCY_REPOS * 2]
    resolved = await asyncio.gather(*(registry.repo_for(p) for p in packages))
    picks: list[RepoPick] = []
    for package, repo in zip(packages, resolved, strict=True):
        if repo and repo.split("/")[0].lower() != fp.login.lower() and repo not in {p.repo for p in picks}:
            picks.append(RepoPick(repo=repo, source="dependency", matched=package))
    return picks[:MAX_DEPENDENCY_REPOS]


# --- Step 3: their issues ------------------------------------------------------


ISSUE_FIELDS = """
      nameWithOwner
      stargazerCount
      issues(first: %d, states: OPEN, labels: %s, orderBy: {field: UPDATED_AT, direction: DESC}) {
        nodes {
          number url title body createdAt updatedAt
          labels(first: 10) { nodes { name } }
          comments { totalCount }
          assignees { totalCount }
          closedByPullRequestsReferences(first: 1, includeClosedPrs: false) { totalCount }
        }
      }
"""


def issues_query(repos: list[tuple[int, str]], labels: list[str]) -> str:
    """One query, one `repository` field per repo, aliased r<index> by its index in the picks."""
    fields = ISSUE_FIELDS % (ISSUES_PER_REPO, json.dumps(labels))
    parts = []
    for i, repo in repos:
        owner, name = repo.split("/", 1)
        parts.append(f"  r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{{fields}  }}")
    return "query RepoIssues {\n" + "\n".join(parts) + "\n}"


def available(issue: dict, fresh_since: datetime) -> bool:
    """Open to a newcomer: nobody assigned, no open PR linked, recently active."""
    return (
        issue["assignees"]["totalCount"] == 0
        and issue["closedByPullRequestsReferences"]["totalCount"] == 0
        and datetime.fromisoformat(issue["updatedAt"]) >= fresh_since
    )


def index_repos(batches: list[list[tuple[int, str]]], responses: list[dict]) -> dict[str, dict]:
    """Requested repo name (lowercase) → its GraphQL data.

    Matches on nameWithOwner; falls back to the alias only for repos that were
    renamed (GitHub returns the new name), so results can't be mislabelled.
    """
    requested = {repo.lower() for batch in batches for _, repo in batch}
    by_repo: dict[str, dict] = {}
    for batch, response in zip(batches, responses, strict=True):
        for repo in response.values():
            if repo:
                by_repo[repo["nameWithOwner"].lower()] = repo
        for i, name in batch:
            aliased = response.get(f"r{i}")
            if aliased and name.lower() not in by_repo and aliased["nameWithOwner"].lower() not in requested:
                by_repo[name.lower()] = aliased
    return by_repo


def merge(picks: list[RepoPick], by_repo: dict[str, dict], seen: set[str], fresh_since: datetime) -> list[Candidate]:
    """Pure: repo data → candidates.

    Interleaves repos (dependencies first: they're the strongest "why"),
    drops seen or unavailable issues, keeps at most PER_REPO per repo.
    """
    queues: list[list[Candidate]] = []
    for pick in sorted(picks, key=lambda p: p.source != "dependency"):
        repo = by_repo.get(pick.repo.lower())
        if not repo:
            continue  # deleted, private, or no access
        queue = []
        for issue in repo["issues"]["nodes"]:
            cid = f"{repo['nameWithOwner']}#{issue['number']}"
            if cid in seen or not available(issue, fresh_since):
                continue
            queue.append(
                Candidate(
                    id=cid,
                    url=issue["url"],
                    repo=repo["nameWithOwner"],
                    repo_stars=repo["stargazerCount"],
                    number=issue["number"],
                    title=issue["title"],
                    body=(issue.get("body") or "")[:2000],
                    labels=[label["name"] for label in issue["labels"]["nodes"]],
                    comments=issue["comments"]["totalCount"],
                    created_at=issue["createdAt"],
                    updated_at=issue["updatedAt"],
                    source=pick.source,
                    matched=pick.matched,
                )
            )
        queues.append(queue[:PER_REPO])

    out: list[Candidate] = []
    for rank in range(PER_REPO):
        out += [q[rank] for q in queues if len(q) > rank]
    return out[:MAX_CANDIDATES]


async def find_candidates(
    github: GitHub, registry: Registry, fp: Fingerprint, seen: set[str], now: datetime | None = None
) -> list[Candidate]:
    now = now or datetime.now(UTC)
    lang_picks, dep_picks = await asyncio.gather(language_repos(github, fp, now.date()), dependency_repos(registry, fp))

    picks: list[RepoPick] = []
    for pick in [*dep_picks, *lang_picks]:
        if pick.repo not in {p.repo for p in picks}:
            picks.append(pick)
    if not picks:
        return []

    indexed = list(enumerate(p.repo for p in picks))
    batches = [indexed[i : i + REPOS_PER_CALL] for i in range(0, len(indexed), REPOS_PER_CALL)]
    responses = await asyncio.gather(*(github.graphql(issues_query(b, LABELS[fp.level])) for b in batches))
    by_repo = index_repos(batches, list(responses))
    return merge(picks, by_repo, seen, fresh_since=now - timedelta(days=FRESH_DAYS))
