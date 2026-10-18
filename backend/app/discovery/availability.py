"""C3: re-check an issue against live GitHub right before the user picks it.

Matches can be up to 15 minutes old (cache). Between seeing a card and
clicking "I'll take this", someone may have been assigned, opened a PR or
claimed it in a comment.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from app.discovery.checks import COMMENT_FIELDS, claim_status
from app.github import GitHub, GitHubError

ISSUE_CHECK_QUERY = (
    """
query IssueCheck($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      title url state
      assignees(first: 1) { nodes { login } }
      closedByPullRequestsReferences(first: 1, includeClosedPrs: false) { nodes { url } }
"""
    + COMMENT_FIELDS
    + """
    }
  }
}
"""
)

Reason = Literal["available", "not_found", "closed", "assigned", "pr_open", "claimed"]


class Availability(BaseModel):
    issue_id: str
    available: bool
    reason: Reason
    message: str
    title: str = ""
    url: str = ""
    detail_url: str | None = None  # the PR or the claiming comment's author, when relevant


def parse_issue_id(issue_id: str) -> tuple[str, str, int]:
    """"owner/repo#123" → ("owner", "repo", 123)."""
    repo, _, number = issue_id.partition("#")
    owner, _, name = repo.partition("/")
    if not owner or not name or not number.isdigit():
        raise ValueError(f"bad issue id {issue_id!r}, expected owner/repo#number")
    return owner, name, int(number)


def evaluate(issue_id: str, data: dict | None, now: datetime) -> Availability:
    """Pure: IssueCheck response → is it still free?"""
    issue = ((data or {}).get("repository") or {}).get("issue")
    if not issue:
        return Availability(issue_id=issue_id, available=False, reason="not_found", message="This issue no longer exists.")

    base = {"issue_id": issue_id, "title": issue["title"], "url": issue["url"]}
    if issue["state"] != "OPEN":
        return Availability(**base, available=False, reason="closed", message="This issue was closed.")
    if assignees := issue["assignees"]["nodes"]:
        return Availability(
            **base, available=False, reason="assigned", message=f"It was just assigned to @{assignees[0]['login']}."
        )
    if prs := issue["closedByPullRequestsReferences"]["nodes"]:
        return Availability(
            **base, available=False, reason="pr_open", message="Someone already opened a PR for it.", detail_url=prs[0]["url"]
        )
    claim = claim_status(issue["comments"]["nodes"], now)
    if claim.claimed:
        return Availability(
            **base, available=False, reason="claimed", message=f"@{claim.by} asked to work on it {(now - claim.at).days} days ago."
        )
    return Availability(**base, available=True, reason="available", message="Still free.")


async def check(github: GitHub, issue_id: str, now: datetime | None = None) -> Availability:
    owner, name, number = parse_issue_id(issue_id)
    try:
        data = await github.graphql(ISSUE_CHECK_QUERY, {"owner": owner, "name": name, "number": number}, fresh=True)
    except GitHubError as e:
        if "Could not resolve" not in str(e):
            raise
        data = None  # repo or issue doesn't exist (or the number is a PR)
    return evaluate(issue_id, data, now or datetime.now(UTC))
