"""One issue, scored for one user (B5 issue page; also B4: any issue, not just matches)."""

import asyncio
from datetime import UTC, datetime

from app.contracts import Fingerprint, IssueDetail, RepoHealth
from app.discovery import checks, rank
from app.discovery.availability import parse_issue_id
from app.discovery.search import Candidate, dependency_repos
from app.fingerprint.builder import LANGUAGE_ALIASES
from app.github import GitHub, GitHubError
from app.registry import Registry

ISSUE_DETAIL_QUERY = """
query IssueDetail($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    stargazerCount
    primaryLanguage { name }
    issue(number: $number) {
      number url title body createdAt updatedAt state
      labels(first: 10) { nodes { name } }
      comments { totalCount }
    }
  }
}
"""


class IssueNotFound(Exception):
    pass


async def issue_detail(github: GitHub, registry: Registry, fp: Fingerprint, issue_id: str) -> IssueDetail:
    owner, name, number = parse_issue_id(issue_id)
    try:
        data = await github.graphql(ISSUE_DETAIL_QUERY, {"owner": owner, "name": name, "number": number})
    except GitHubError as e:
        if "Could not resolve" in str(e):
            raise IssueNotFound from e
        raise
    repo = (data or {}).get("repository") or {}
    issue = repo.get("issue")
    if not issue:
        raise IssueNotFound

    # Which of the user's skills does this draw on: a dependency, else the repo's main language.
    deps = {p.repo.lower(): p for p in await dependency_repos(registry, fp)}
    if dep := deps.get(repo["nameWithOwner"].lower()):
        source, matched = "dependency", dep.matched
    else:
        language = ((repo.get("primaryLanguage") or {}).get("name") or "").lower()
        source, matched = "language", LANGUAGE_ALIASES.get(language, language) or "any"

    candidate = Candidate(
        id=f"{repo['nameWithOwner']}#{issue['number']}",
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
        source=source,
        matched=matched,
    )
    now = datetime.now(UTC)
    stats, claims = await asyncio.gather(
        checks.fetch_repo_stats(github, [candidate.repo], now),
        checks.fetch_claims(github, [candidate], now),
    )
    s, claim = stats[candidate.repo], claims[candidate.id]
    return IssueDetail(
        card=rank.score(candidate, fp, s, claim, now),
        body=issue.get("body") or "",
        comments=candidate.comments,
        claimed_by=claim.by if claim.claimed else None,
        repo=RepoHealth(
            repo=candidate.repo,
            stars=candidate.repo_stars,
            reply_hours=s.reply_hours,
            newcomer_merges_90d=s.newcomer_merges_90d,
            newcomer_merged=s.newcomer_merged,
            newcomer_closed=s.newcomer_closed,
        ),
    )
