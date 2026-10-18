"""Endpoints behind the product UI (mock mode, recorded fixtures)."""

from httpx import ASGITransport, AsyncClient

from app.contracts import Fingerprint, Skill
from app.graph import progress
from app.main import app

ISSUE = "CesiumGS/cesium#5315"  # matches the IssueDetail / IssueCheck fixtures
ISSUE_PATH = "CesiumGS/cesium/5315"


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def make_user():
    await progress.upsert_user(
        Fingerprint(login="maya", level="beginner", skills=[Skill(tech="javascript", kind="language", level=0.9)])
    )


async def test_preferences_roundtrip(graph):
    await make_user()
    async with client() as c:
        resp = await c.put("/users/maya/preferences", json={"languages": ["typescript"], "difficulty": "medium", "hours_per_week": 5})
        assert resp.status_code == 200
        assert resp.json()["preferences"] == {"languages": ["typescript"], "difficulty": "medium", "hours_per_week": 5}
        assert (await c.put("/users/ghost/preferences", json={})).status_code == 404


async def test_issue_detail_scores_issue_and_feeds_the_why_graph(graph):
    await make_user()
    async with client() as c:
        detail = (await c.get(f"/users/maya/issues/{ISSUE_PATH}")).json()
        assert detail["card"]["id"] == ISSUE
        assert detail["card"]["tech"] == "javascript"
        assert set(detail["card"]["breakdown"]) == {"skill", "difficulty", "maintainer", "newcomers", "freshness"}
        assert detail["repo"]["repo"] == "CesiumGS/cesium"
        assert detail["attempt_id"] is None

        why = (await c.get(f"/users/maya/issues/{ISSUE_PATH}/why")).json()
    kinds = {n["kind"] for n in why["nodes"]}
    assert {"user", "tech", "issue", "repo"} <= kinds
    assert {"label": "NEEDS", "source": "issue", "target": "tech"} in why["edges"]
    assert any(e["label"].startswith("KNOWS") for e in why["edges"])
    assert "MATCH" in why["cypher"]


async def test_why_404_before_issue_is_in_graph(graph):
    await make_user()
    async with client() as c:
        assert (await c.get("/users/maya/issues/a/b/1/why")).status_code == 404


async def test_save_list_unsave(graph):
    await make_user()
    async with client() as c:
        card = (await c.get(f"/users/maya/issues/{ISSUE_PATH}")).json()["card"]
        assert (await c.post("/users/maya/saved", json=card)).status_code == 204
        saved = (await c.get("/users/maya/saved")).json()
        assert [s["id"] for s in saved] == [ISSUE] and saved[0]["saved"]
        assert (await c.get(f"/users/maya/issues/{ISSUE_PATH}")).json()["card"]["saved"]

        assert (await c.delete(f"/users/maya/saved/{ISSUE_PATH}")).status_code == 204
        assert (await c.get("/users/maya/saved")).json() == []


async def test_attempt_lookup_and_trail_graph(graph):
    await make_user()
    async with client() as c:
        await c.get(f"/users/maya/issues/{ISSUE_PATH}")  # shown → issue NEEDS javascript
        assert (await c.post("/users/maya/attempts", json={"issue_id": ISSUE})).status_code == 201

        attempt = (await c.get(f"/users/maya/attempts/{ISSUE_PATH}")).json()
        assert attempt["status"] == "selected"
        assert (await c.get(f"/users/maya/issues/{ISSUE_PATH}")).json()["attempt_id"] == attempt["id"]
        assert (await c.get("/users/maya/attempts/a/b/1")).status_code == 404

        trail = (await c.get("/users/maya/graph")).json()
    ids = {n["id"] for n in trail["nodes"]}
    assert {"user", "tech:javascript", f"issue:{ISSUE}", "repo:CesiumGS/cesium"} <= ids
    assert {"source": "user", "target": f"issue:{ISSUE}", "label": "selected"} in trail["edges"]
