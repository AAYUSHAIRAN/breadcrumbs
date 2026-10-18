"""Skill fingerprint (A1): what a GitHub user knows, from their public repos.

One GraphQL call fetches repos, language bytes, dependency-file contents and
merged PRs to other people's repos.

Scoring, per tech:
    evidence = Σ own repos:   recency × share of that repo
                              (language: share of bytes; library: 1 if a dependency)
             + Σ merged PRs:  recency × MERGED_PR_WEIGHT  (repo's main language)
    level    = 1 − e^(−evidence / 2)
so one recent repo ≈ 0.4, three ≈ 0.8. Recency halves every two years.
A merged PR counts more than an own repo: someone else accepted the code.
"""

import math
from collections import Counter, defaultdict
from datetime import UTC, datetime

from app.contracts import Fingerprint, Level, Skill
from app.fingerprint.deps import KNOWN, PARSERS
from app.github import GitHub, GitHubError

QUERY = """
query UserFingerprint($login: String!, $mergedQuery: String!) {
  user(login: $login) {
    login
    name
    avatarUrl
    repositories(first: 40, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        nameWithOwner
        pushedAt
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
        packageJson: object(expression: "HEAD:package.json") { ... on Blob { text } }
        requirements: object(expression: "HEAD:requirements.txt") { ... on Blob { text } }
        pyproject: object(expression: "HEAD:pyproject.toml") { ... on Blob { text } }
      }
    }
  }
  merged: search(query: $mergedQuery, type: ISSUE, first: 30) {
    issueCount
    nodes {
      ... on PullRequest {
        mergedAt
        repository { nameWithOwner primaryLanguage { name } }
      }
    }
  }
}
"""

# GitHub language name → our tech name. None = not a skill worth matching on.
LANGUAGE_ALIASES: dict[str, str | None] = {
    "jupyter notebook": "python",
    "html": None,
    "css": None,
    "scss": None,
    "dockerfile": None,
    "makefile": None,
    "procfile": None,
    "batchfile": None,
    "powershell": None,
}

HALF_LIFE_DAYS = 730
MERGED_PR_WEIGHT = 1.5
MAX_DEPENDENCIES = 50


class UserNotFound(Exception):
    pass


def recency(pushed_at: str, now: datetime) -> float:
    age_days = (now - datetime.fromisoformat(pushed_at)).days
    return 0.5 ** (max(age_days, 0) / HALF_LIFE_DAYS)


def saturate(evidence: float) -> float:
    return round(1 - math.exp(-evidence / 2), 3)


def overall_level(merged_prs: int, merged_repos: int, skills: list[Skill]) -> Level:
    """Advanced needs breadth (many merges in one repo is a regular, not a seasoned
    contributor) or sheer volume. merged_repos only sees the 30 most recent PRs, so
    a core maintainer of one big project would look narrow without the volume rule."""
    strongest = max((s.level for s in skills), default=0)
    if merged_prs >= 100 or (merged_prs >= 10 and merged_repos >= 3):
        return "advanced"
    if merged_prs >= 1 or strongest >= 0.8:
        return "intermediate"
    return "beginner"


def build(data: dict, now: datetime | None = None) -> Fingerprint:
    """Pure: GraphQL response → Fingerprint. Kept separate from I/O for testing."""
    now = now or datetime.now(UTC)
    user = data.get("user")
    if not user:
        raise UserNotFound
    repos = user["repositories"]["nodes"]

    evidence: dict[tuple[str, str], float] = defaultdict(float)
    dependency_counts: Counter[str] = Counter()

    for repo in repos:
        weight = recency(repo["pushedAt"], now)

        edges = repo["languages"]["edges"]
        total = sum(e["size"] for e in edges) or 1
        for edge in edges:
            name = edge["node"]["name"].lower()
            tech = LANGUAGE_ALIASES.get(name, name)
            if tech:
                evidence[(tech, "language")] += weight * edge["size"] / total

        packages: set[str] = set()
        for field, parse in PARSERS.items():
            if blob := repo.get(field):
                packages |= parse(blob["text"])
        dependency_counts.update(packages)
        for package in packages:
            if package in KNOWN:
                tech, kind = KNOWN[package]
                evidence[(tech, kind)] += weight

    for pr in data["merged"]["nodes"]:
        language = (pr["repository"].get("primaryLanguage") or {}).get("name", "").lower()
        tech = LANGUAGE_ALIASES.get(language, language)
        if tech:
            evidence[(tech, "language")] += recency(pr["mergedAt"], now) * MERGED_PR_WEIGHT

    skills = sorted(
        (Skill(tech=tech, kind=kind, level=saturate(ev)) for (tech, kind), ev in evidence.items()),
        key=lambda s: s.level,
        reverse=True,
    )
    skills = [s for s in skills if s.level >= 0.05]
    merged = data["merged"]["issueCount"]
    merged_repos = len({pr["repository"]["nameWithOwner"] for pr in data["merged"]["nodes"]})

    return Fingerprint(
        login=user["login"],
        name=user.get("name"),
        avatar_url=user.get("avatarUrl"),
        level=overall_level(merged, merged_repos, skills),
        skills=skills,
        merged_prs=merged,
        dependencies=[p for p, _ in dependency_counts.most_common(MAX_DEPENDENCIES)],
    )


async def fetch(github: GitHub, login: str) -> dict:
    # Merged PRs to repos the user doesn't own: real open-source contributions.
    merged_query = f"author:{login} is:pr is:merged -user:{login}"
    try:
        return await github.graphql(QUERY, {"login": login, "mergedQuery": merged_query})
    except GitHubError as e:
        if "Could not resolve to a User" in str(e):
            raise UserNotFound from e
        raise


async def fingerprint(github: GitHub, login: str) -> Fingerprint:
    return build(await fetch(github, login))
