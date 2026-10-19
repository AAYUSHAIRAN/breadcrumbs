from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.contracts import Fingerprint, Preferences, Skill
from app.discovery import search
from app.discovery.checks import Claim, RepoStats, claim_status, index_comments, repo_stats
from app.discovery.matches import diversify
from app.discovery.rank import difficulty, difficulty_fit, score, target_difficulty
from app.discovery.search import Candidate
from app.main import app

NOW = datetime(2026, 10, 18, tzinfo=UTC)
USER = {"__typename": "User", "login": "newbie"}
MAINT = {"__typename": "User", "login": "maint"}
BOT = {"__typename": "Bot", "login": "dependabot"}


def ago(**kw) -> str:
    return (NOW - timedelta(**kw)).isoformat()


# --- Repo stats --------------------------------------------------------------------


def pr(author, association="CONTRIBUTOR", merged=True, created=None, reply_after_h=None, replier=MAINT):
    created = created or ago(days=10)
    replies = []
    if reply_after_h is not None:
        at = (datetime.fromisoformat(created) + timedelta(hours=reply_after_h)).isoformat()
        replies = [{"createdAt": at, "author": replier}]
    return {
        "createdAt": created,
        "mergedAt": ago(days=9) if merged else None,
        "closedAt": ago(days=9),
        "authorAssociation": association,
        "author": author,
        "reviews": {"nodes": replies},
        "comments": {"nodes": []},
    }


def stats_for(*prs):
    return repo_stats("a/b", {"repository": {"nameWithOwner": "a/b", "pullRequests": {"nodes": list(prs)}}}, NOW)


def test_bots_and_maintainers_are_not_newcomers():
    s = stats_for(
        pr(USER),
        pr(BOT),
        pr({"__typename": "User", "login": "renovate-bot"}),
        pr(MAINT, association="MEMBER"),
    )
    assert s.newcomer_merges_90d == 1


def test_repeat_authors_are_not_newcomers():
    s = stats_for(pr(USER), pr(USER), pr({"__typename": "User", "login": "fresh"}, merged=False))
    assert (s.newcomer_merged, s.newcomer_closed) == (0, 1)


def test_reply_time_ignores_bots_and_the_author():
    s = stats_for(
        pr(USER, reply_after_h=2),
        pr({"__typename": "User", "login": "x"}, reply_after_h=1, replier=BOT),
        pr({"__typename": "User", "login": "y"}, reply_after_h=1, replier={"__typename": "User", "login": "y"}),
        pr({"__typename": "User", "login": "z"}, reply_after_h=10),
    )
    assert s.reply_hours == 6.0  # median of 2h and 10h only


def test_missing_repo_gives_empty_stats():
    s = repo_stats("gone/repo", {"repository": None}, NOW)
    assert s.reply_hours is None and s.newcomer_merges_90d == 0


# --- Claims ------------------------------------------------------------------------------


def comment(body, days_ago, author=USER, association="NONE"):
    return {"body": body, "createdAt": ago(days=days_ago), "author": author, "authorAssociation": association}


def test_recent_claim_is_live():
    c = claim_status([comment("Hi! Can I work on this?", 3)], NOW)
    assert c.claimed and c.by == "newbie"


def test_old_unanswered_claim_expires():
    c = claim_status([comment("I'd like to work on this", 40)], NOW)
    assert not c.claimed and c.expired


def test_maintainer_go_ahead_keeps_old_claim_live():
    c = claim_status(
        [comment("please assign me", 40), comment("Sure, go ahead!", 39, MAINT, "MEMBER")],
        NOW,
    )
    assert c.claimed and c.acknowledged


def test_ordinary_comments_and_maintainers_are_not_claims():
    c = claim_status(
        [comment("This also happens on Firefox", 2), comment("I'll take a look at this", 1, MAINT, "OWNER")],
        NOW,
    )
    assert not c.claimed and not c.expired


def test_comments_are_indexed_by_issue_not_alias():
    response = {"i0": {"issue": {"number": 7, "repository": {"nameWithOwner": "a/b"}, "comments": {"nodes": [1]}}}}
    assert index_comments([response, {"i0": None}]) == {"a/b#7": [1]}


# --- Scoring -------------------------------------------------------------------------------


def candidate(**kw):
    base = {
        "id": "a/b#1",
        "url": "u",
        "repo": "a/b",
        "repo_stars": 1000,
        "number": 1,
        "title": "t",
        "body": "",
        "labels": ["good first issue"],
        "comments": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "source": "language",
        "matched": "python",
    }
    return Candidate(**(base | kw))


FP = Fingerprint(login="maya", level="beginner", skills=[Skill(tech="python", kind="language", level=0.8)])
GOOD_REPO = RepoStats(repo="a/b", reply_hours=4, newcomer_merges_90d=6, newcomer_merged=6, newcomer_closed=1)
FREE = Claim(claimed=False)


def test_difficulty_from_labels_and_size():
    assert difficulty(["good first issue"], "short") == "easy"
    assert difficulty(["good first issue"], "x" * 3000) == "medium"
    assert difficulty(["help wanted", "performance"], "") == "hard"
    assert difficulty(["bug"], "") == "medium"


def test_difficulty_targets_level_unless_the_user_chose():
    assert target_difficulty(FP) == "easy"
    chose_hard = FP.model_copy(update={"preferences": Preferences(difficulty="hard")})
    assert target_difficulty(chose_hard) == "hard"
    assert difficulty_fit("easy", "easy") == 1
    assert difficulty_fit("hard", "easy") == 0


def test_card_carries_breakdown_and_tech():
    card = score(candidate(), FP, GOOD_REPO, FREE, NOW)
    assert card.tech == "python"
    assert set(card.breakdown) == {"skill", "difficulty", "maintainer", "newcomers", "freshness"}
    assert all(0 <= v <= 1 for v in card.breakdown.values())


def test_claimed_issue_ranks_far_lower_and_says_why():
    free = score(candidate(), FP, GOOD_REPO, FREE, NOW)
    taken = score(candidate(), FP, GOOD_REPO, Claim(claimed=True, by="someone", at=NOW - timedelta(days=2)), NOW)
    assert taken.fit < free.fit * 0.5
    assert taken.claimed
    assert any(w.kind == "warning" and "@someone" in w.label for w in taken.why)


def test_responsive_repo_beats_silent_one():
    silent = RepoStats(repo="a/b", reply_hours=24 * 20, newcomer_merges_90d=0, newcomer_merged=0, newcomer_closed=5)
    good = score(candidate(), FP, GOOD_REPO, FREE, NOW)
    bad = score(candidate(), FP, silent, FREE, NOW)
    assert good.fit > bad.fit and good.merge_forecast > bad.merge_forecast
    assert any("slow to reply" in w.label for w in bad.why)
    assert {"fast_maintainer", "newcomers", "unclaimed", "small_scope", "skill"} <= {w.kind for w in good.why}


def test_dependency_issue_gets_floor_skill_and_chip():
    card = score(candidate(source="dependency", matched="pypi:fastapi"), FP, GOOD_REPO, FREE, NOW)
    assert card.in_dependencies
    assert card.why[0].kind == "dependency" and "fastapi" in card.why[0].label


def test_diversify_spreads_repos():
    cards = [
        score(candidate(id=i, repo=r), FP, GOOD_REPO, FREE, NOW)
        for i, r in [("a/b#1", "a/b"), ("a/b#2", "a/b"), ("c/d#1", "c/d")]
    ]
    assert [c.id for c in diversify(cards)] == ["a/b#1", "c/d#1", "a/b#2"]


# --- Endpoint (mock mode, recorded fixtures) -----------------------------------------------


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


async def test_matches_endpoint_ranks_and_remembers_what_it_showed(graph, monkeypatch):
    import app.discovery.matches as matches_module

    monkeypatch.setattr(search, "datetime", _FrozenDatetime)
    monkeypatch.setattr(matches_module, "datetime", _FrozenDatetime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/users/AAYUSHAIRAN/matches")).json()

    issues = body["issues"]
    assert issues
    fits = [i["fit"] for i in issues]
    firsts = fits[: len({i["repo"] for i in issues})]
    assert firsts == sorted(firsts, reverse=True)
    assert all(i["why"] for i in issues)

    rows = (await graph.query("MATCH (:User {login: 'AAYUSHAIRAN'})-[s:SHOWN]->(i:Issue) RETURN count(i)")).result_set
    assert rows[0][0] == len(issues)


def test_technology_the_user_chose_counts_as_a_medium_skill():
    chose_rust = FP.model_copy(update={"preferences": Preferences(languages=["rust"])})
    card = score(candidate(matched="rust"), chose_rust, GOOD_REPO, FREE, NOW)
    assert card.breakdown["skill"] == 0.5
    assert score(candidate(matched="rust"), FP, GOOD_REPO, FREE, NOW).breakdown["skill"] == 0


async def test_matches_pages_through_the_ranked_list(graph, monkeypatch):
    import app.discovery.matches as matches_module

    monkeypatch.setattr(search, "datetime", _FrozenDatetime)
    monkeypatch.setattr(matches_module, "datetime", _FrozenDatetime)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        everything = (await client.get("/users/AAYUSHAIRAN/matches")).json()
        first = (await client.get("/users/AAYUSHAIRAN/matches?page=1&page_size=3")).json()
        second = (await client.get("/users/AAYUSHAIRAN/matches?page=2&page_size=3")).json()
        past_end = (await client.get("/users/AAYUSHAIRAN/matches?page=99&page_size=3")).json()
    assert everything["page_size"] == 0 and len(everything["issues"]) == everything["total"]
    ids = [i["id"] for i in everything["issues"]]
    assert [i["id"] for i in first["issues"]] == ids[:3]
    assert [i["id"] for i in second["issues"]] == ids[3:6]
    assert first["total"] == everything["total"] and first["page_size"] == 3
    assert past_end["issues"] == []
