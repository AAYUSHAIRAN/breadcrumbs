from datetime import UTC, date, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.contracts import Fingerprint, Preferences, Skill
from app.discovery import search
from app.discovery.search import RepoPick, available, index_repos, merge
from app.graph import progress
from app.main import app
from app.registry import Registry, github_repo_from_url

NOW = datetime(2026, 10, 18, tzinfo=UTC)
FRESH = NOW - timedelta(days=60)


def fp(level="beginner", skills=(("python", "language", 0.8),), deps=()):
    return Fingerprint(
        login="maya",
        level=level,
        skills=[Skill(tech=t, kind=k, level=lv) for t, k, lv in skills],
        dependencies=list(deps),
    )


def issue(number, assignees=0, linked_prs=0, updated=NOW):
    return {
        "number": number,
        "url": f"https://github.com/x/y/issues/{number}",
        "title": f"Issue {number}",
        "body": "",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": updated.isoformat(),
        "labels": {"nodes": [{"name": "good first issue"}]},
        "comments": {"totalCount": 0},
        "assignees": {"totalCount": assignees},
        "closedByPullRequestsReferences": {"totalCount": linked_prs},
    }


def repo(name, *issues, stars=1000):
    return {"nameWithOwner": name, "stargazerCount": stars, "issues": {"nodes": list(issues)}}


# --- Queries -------------------------------------------------------------------


def test_repo_query_targets_level_and_excludes_own_repos():
    q = search.repo_query(fp("beginner"), "c++", date(2026, 10, 18))
    assert 'language:"c++"' in q
    assert "good-first-issues:>=3" in q
    assert "pushed:>=2026-09-18" in q
    assert "-user:maya" in q
    assert "help-wanted-issues" in search.repo_query(fp("advanced"), "go", date(2026, 10, 18))


def test_top_languages_skips_weak_ones_but_never_returns_nothing():
    strong = fp(skills=[("python", "language", 0.9), ("go", "language", 0.05), ("react", "framework", 0.9)])
    assert search.top_languages(strong) == ["python"]
    weak = fp(skills=[("go", "language", 0.05)])
    assert search.top_languages(weak) == ["go"]


def test_chosen_languages_override_skills():
    user = fp(skills=[("python", "language", 0.9)]).model_copy(update={"preferences": Preferences(languages=["rust", "go"])})
    assert search.top_languages(user) == ["rust", "go"]


def test_issues_query_aliases_by_pick_index_and_escapes_names():
    q = search.issues_query([(3, 'a/b"c')], ["good first issue"])
    assert q.startswith("query RepoIssues {")
    assert 'r3: repository(owner: "a", name: "b\\"c")' in q
    assert 'labels: ["good first issue"]' in q


# --- Filtering and merging ---------------------------------------------------------


def test_unavailable_issues_are_dropped():
    assert available(issue(1), FRESH)
    assert not available(issue(2, assignees=1), FRESH)
    assert not available(issue(3, linked_prs=1), FRESH)
    assert not available(issue(4, updated=NOW - timedelta(days=90)), FRESH)


def test_merge_puts_dependencies_first_caps_repos_and_skips_seen():
    picks = [
        RepoPick(repo="lang/busy", source="language", matched="python"),
        RepoPick(repo="dep/lib", source="dependency", matched="pypi:lib"),
    ]
    by_repo = {
        "lang/busy": repo("lang/busy", issue(1), issue(2), issue(3), issue(4)),
        "dep/lib": repo("dep/lib", issue(9), issue(10)),
    }
    out = merge(picks, by_repo, seen={"lang/busy#1"}, fresh_since=FRESH)
    assert [c.id for c in out] == ["dep/lib#9", "lang/busy#2", "dep/lib#10", "lang/busy#3"]
    assert out[0].source == "dependency" and out[0].matched == "pypi:lib"


def test_index_repos_handles_renames_without_mislabelling():
    batches = [[(0, "old/name"), (1, "a/b")]]
    response = {"r0": repo("new/name"), "r1": repo("a/b")}
    by_repo = index_repos(batches, [response])
    assert by_repo["old/name"]["nameWithOwner"] == "new/name"
    assert by_repo["a/b"]["nameWithOwner"] == "a/b"

    # An alias pointing at another requested repo is not a rename.
    by_repo = index_repos([[(0, "missing/repo"), (1, "a/b")]], [{"r0": repo("a/b"), "r1": None}])
    assert "missing/repo" not in by_repo


# --- Dependencies (B3) --------------------------------------------------------------


def test_github_repo_from_registry_urls():
    assert github_repo_from_url("git+https://github.com/facebook/react.git") == "facebook/react"
    assert github_repo_from_url("https://github.com/fastapi/fastapi/tree/main") == "fastapi/fastapi"
    assert github_repo_from_url("git@github.com:a/b.git") == "a/b"
    assert github_repo_from_url("https://gitlab.com/a/b") is None


async def test_dependency_repos_skip_tooling_and_own_repos():
    user = fp(deps=["npm:typescript", "npm:@types/node", "npm:react", "npm:maya-utils", "pypi:fastapi"])
    registry = Registry(cache=None)  # mock lookups
    registry.repo_for = _fake_lookup({"npm:react": "facebook/react", "npm:maya-utils": "maya/utils", "pypi:fastapi": "fastapi/fastapi"})
    picks = await search.dependency_repos(registry, user)
    assert [p.repo for p in picks] == ["facebook/react", "fastapi/fastapi"]


def _fake_lookup(table):
    async def lookup(package):
        return table.get(package)

    return lookup


# --- Endpoint (mock mode, recorded fixtures) ---------------------------------------------


async def test_candidates_endpoint_excludes_skipped_issues(graph, monkeypatch):
    monkeypatch.setattr(search, "datetime", _FrozenDatetime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.get("/users/AAYUSHAIRAN/candidates")).json()
        assert first["candidates"]
        assert len({c["repo"] for c in first["candidates"]}) > 1

        skipped = first["candidates"][0]["id"]
        await progress.skip_issue("AAYUSHAIRAN", skipped, "not_interested")
        second = (await client.get("/users/AAYUSHAIRAN/candidates")).json()
    assert skipped not in {c["id"] for c in second["candidates"]}


class _FrozenDatetime(datetime):
    """Fixtures were recorded on 2026-10-18; pin "now" so the freshness filter is stable."""

    @classmethod
    def now(cls, tz=None):
        return NOW
