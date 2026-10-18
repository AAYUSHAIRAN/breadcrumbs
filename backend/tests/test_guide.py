from httpx import ASGITransport, AsyncClient

from app.agent import memory
from app.agent.guide import Fact, _repo_files_query, _save_repo_facts, repo_facts
from app.contracts import Fingerprint
from app.graph import progress
from app.main import app

ISSUE = "CesiumGS/cesium#5315"


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_repo_rules_query_asks_for_rule_files_in_one_call():
    q, aliases = _repo_files_query("a", "b")
    assert q.startswith("query RepoRules")
    assert "CONTRIBUTING.md" in aliases.values() and ".github/PULL_REQUEST_TEMPLATE.md" in aliases.values()
    assert ".github/workflows" in q


async def test_repo_facts_are_shared_and_deduplicated(graph):
    await _save_repo_facts("a/b", [Fact(fact="Uses pnpm", source="package.json")])
    await _save_repo_facts("a/b", [Fact(fact="uses pnpm", source="CONTRIBUTING.md")])
    assert await repo_facts("a/b") == [{"fact": "Uses pnpm", "source": "package.json"}]


async def test_memory_roundtrip_and_forget(graph):
    await progress.upsert_user(Fingerprint(login="maya", level="beginner", skills=[]))
    await memory.remember("maya", "Only free on weekends", "availability", "s1")
    async with client() as c:
        mems = (await c.get("/users/maya/memory")).json()["memories"]
        assert [m["text"] for m in mems] == ["Only free on weekends"]
        assert (await c.delete(f"/users/maya/memory/{mems[0]['id']}")).status_code == 204
        assert (await c.get("/users/maya/memory")).json()["memories"] == []


async def test_guide_without_llm_key_explains_itself(graph):
    await progress.upsert_user(Fingerprint(login="maya", level="beginner", skills=[]))
    async with client() as c:
        await c.post("/users/maya/attempts", json={"issue_id": ISSUE})
        assert (await c.get("/users/maya/attempts/CesiumGS/cesium/5315/guide")).json() == {}
        resp = await c.post("/users/maya/attempts/CesiumGS/cesium/5315/guide")
    assert resp.status_code == 503
    assert "LLM_API_KEY" in resp.json()["detail"]  # mock mode never calls a model
