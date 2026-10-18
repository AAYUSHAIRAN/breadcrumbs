import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.fingerprint.builder import UserNotFound, build, overall_level
from app.fingerprint.deps import parse_package_json, parse_pyproject, parse_requirements
from app.main import app

FIXTURE = Path(__file__).parent.parent / "fixtures/github/graphql/UserFingerprint.json"
NOW = datetime(2026, 10, 18, tzinfo=UTC)


def repo(pushed_at, languages, package_json=None):
    return {
        "nameWithOwner": "me/r",
        "pushedAt": pushed_at,
        "languages": {"edges": [{"size": size, "node": {"name": name}} for name, size in languages]},
        "packageJson": {"text": json.dumps(package_json)} if package_json else None,
        "requirements": None,
        "pyproject": None,
    }


def response(repos, merged_prs=()):
    return {
        "user": {"login": "me", "name": None, "avatarUrl": None, "repositories": {"nodes": repos}},
        "merged": {
            "issueCount": len(merged_prs),
            "nodes": [
                {"mergedAt": at, "repository": {"nameWithOwner": r, "primaryLanguage": {"name": lang}}}
                for r, lang, at in merged_prs
            ],
        },
    }


# --- Dependency parsing ------------------------------------------------------


def test_package_json_includes_dev_dependencies():
    text = json.dumps({"dependencies": {"react": "^19"}, "devDependencies": {"jest": "^30"}})
    assert parse_package_json(text) == {"npm:react", "npm:jest"}


def test_requirements_strips_versions_comments_and_flags():
    text = "Django>=5.0  # web\n-r base.txt\nscikit_learn==1.5\n\n"
    assert parse_requirements(text) == {"pypi:django", "pypi:scikit-learn"}


def test_pyproject_reads_project_groups_and_poetry():
    text = """
[project]
dependencies = ["fastapi>=0.1"]
[dependency-groups]
dev = ["pytest"]
[tool.poetry.dependencies]
python = "^3.12"
pandas = "*"
"""
    assert parse_pyproject(text) == {"pypi:fastapi", "pypi:pytest", "pypi:pandas"}


def test_broken_files_are_ignored():
    assert parse_package_json("{not json") == set()
    assert parse_pyproject("[[[") == set()


# --- Scoring -----------------------------------------------------------------


def test_recent_repos_count_more_than_old_ones():
    fp = build(
        response([
            repo("2026-10-01T00:00:00Z", [("Python", 100)]),
            repo("2018-01-01T00:00:00Z", [("Go", 100)]),
        ]),
        now=NOW,
    )
    levels = {s.tech: s.level for s in fp.skills}
    assert levels["python"] > 0.35
    assert "go" not in levels  # 8+ years old: below the noise floor


def test_markup_is_not_a_skill_and_notebooks_count_as_python():
    fp = build(response([repo("2026-10-01T00:00:00Z", [("HTML", 50), ("Jupyter Notebook", 50)])]), now=NOW)
    assert {s.tech for s in fp.skills} == {"python"}


def test_known_dependencies_become_skills_and_all_are_kept():
    fp = build(
        response([repo("2026-10-01T00:00:00Z", [("TypeScript", 1)], {"dependencies": {"react": "1", "left-pad": "1"}})]),
        now=NOW,
    )
    assert "react" in {s.tech for s in fp.skills}
    assert set(fp.dependencies) == {"npm:react", "npm:left-pad"}


def test_merged_prs_add_evidence_for_the_repo_language():
    prs = [("other/lib", "Rust", "2026-09-01T00:00:00Z")] * 3
    fp = build(response([], merged_prs=prs), now=NOW)
    assert fp.skills[0].tech == "rust"
    assert fp.skills[0].level > 0.8


def test_level_needs_breadth_for_advanced():
    assert overall_level(0, 0, []) == "beginner"
    assert overall_level(1, 1, []) == "intermediate"
    assert overall_level(17, 1, []) == "intermediate"  # many PRs, one repo
    assert overall_level(12, 4, []) == "advanced"
    assert overall_level(2860, 1, []) == "advanced"  # core maintainer of one big project


def test_unknown_user():
    with pytest.raises(UserNotFound):
        build({"user": None, "merged": {"issueCount": 0, "nodes": []}})


# --- Endpoint (mock mode, recorded fixture) ----------------------------------


def test_recorded_fixture_builds():
    fp = build(json.loads(FIXTURE.read_text()), now=NOW)
    assert fp.login == "AAYUSHAIRAN"
    assert fp.skills


async def test_endpoint_saves_fingerprint_to_graph(graph):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/users/AAYUSHAIRAN/fingerprint")
    assert resp.status_code == 200
    body = resp.json()
    assert body["login"] == "AAYUSHAIRAN"
    assert body["skills"]

    rows = (await graph.query("MATCH (:User {login: 'AAYUSHAIRAN'})-[:KNOWS]->(t:Tech) RETURN count(t)")).result_set
    assert rows[0][0] == len(body["skills"])
