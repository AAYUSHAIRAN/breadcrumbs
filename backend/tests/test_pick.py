from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.contracts import Fingerprint
from app.discovery.availability import evaluate, parse_issue_id
from app.graph import progress
from app.main import app

NOW = datetime(2026, 10, 18, tzinfo=UTC)
ISSUE = "CesiumGS/cesium#5315"  # matches the recorded IssueCheck fixture


def issue_data(state="OPEN", assignees=(), prs=(), comments=()):
    return {
        "repository": {
            "issue": {
                "title": "T",
                "url": "https://github.com/a/b/issues/1",
                "state": state,
                "assignees": {"nodes": [{"login": a} for a in assignees]},
                "closedByPullRequestsReferences": {"nodes": [{"url": u} for u in prs]},
                "number": 1,
                "repository": {"nameWithOwner": "a/b"},
                "comments": {"nodes": list(comments)},
            }
        }
    }


def test_parse_issue_id():
    assert parse_issue_id("a/b#12") == ("a", "b", 12)
    with pytest.raises(ValueError):
        parse_issue_id("a/b")


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (issue_data(), "available"),
        (issue_data(state="CLOSED"), "closed"),
        (issue_data(assignees=["sam"]), "assigned"),
        (issue_data(prs=["https://github.com/a/b/pull/2"]), "pr_open"),
        (
            issue_data(
                comments=[
                    {
                        "body": "can I take this?",
                        "createdAt": (NOW - timedelta(days=1)).isoformat(),
                        "authorAssociation": "NONE",
                        "author": {"__typename": "User", "login": "sam"},
                    }
                ]
            ),
            "claimed",
        ),
        ({"repository": None}, "not_found"),
        (None, "not_found"),
    ],
)
def test_evaluate(data, reason):
    result = evaluate("a/b#1", data, NOW)
    assert result.reason == reason
    assert result.available == (reason == "available")


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_pick_starts_attempt_and_hides_issue_from_matches(graph):
    await progress.upsert_user(Fingerprint(login="maya", level="beginner", skills=[]))
    async with await _client() as client:
        resp = await client.post("/users/maya/attempts", json={"issue_id": ISSUE})
    assert resp.status_code == 201
    attempt = resp.json()
    assert attempt["status"] == "selected"
    assert attempt["issue_url"].endswith("/issues/5315")
    assert ISSUE in await progress.seen_issue_ids("maya")


async def test_pick_unknown_user_is_404(graph):
    async with await _client() as client:
        resp = await client.post("/users/ghost/attempts", json={"issue_id": ISSUE})
    assert resp.status_code == 404


async def test_pick_rejects_bad_issue_id(graph):
    await progress.upsert_user(Fingerprint(login="maya", level="beginner", skills=[]))
    async with await _client() as client:
        resp = await client.post("/users/maya/attempts", json={"issue_id": "not-an-id"})
    assert resp.status_code == 422


async def test_skip_records_reason(graph):
    await progress.upsert_user(Fingerprint(login="maya", level="beginner", skills=[]))
    async with await _client() as client:
        resp = await client.post("/users/maya/issues/a/b/7/skip", json={"reason": "too_hard"})
    assert resp.status_code == 204
    assert "a/b#7" in await progress.seen_issue_ids("maya")
    rows = (await graph.query("MATCH (:User {login:'maya'})-[s:SKIPPED]->(:Issue {id:'a/b#7'}) RETURN s.reason")).result_set
    assert rows == [["too_hard"]]
