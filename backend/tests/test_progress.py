from datetime import UTC, datetime, timedelta

from app.contracts import Event, Fingerprint, Skill
from app.graph import progress

T0 = datetime.now(UTC) + timedelta(minutes=5)  # synced activity happens after the pick
ISSUE = "acme/widgets#42"


async def make_user(login="maya"):
    await progress.upsert_user(
        Fingerprint(
            login=login,
            level="beginner",
            skills=[
                Skill(tech="typescript", kind="language", level=0.6),
                Skill(tech="react", kind="framework", level=0.4),
            ],
        )
    )


async def test_user_roundtrip_keeps_manual_and_learned_skills(graph):
    await make_user()
    await progress.learn("maya", {"jest": "library"})
    # Re-fingerprinting replaces inferred skills but keeps learned ones.
    await progress.upsert_user(
        Fingerprint(login="maya", level="beginner", skills=[Skill(tech="python", kind="language", level=0.5)])
    )
    user = await progress.get_user("maya")
    assert {s.tech for s in user.skills} == {"python", "jest"}


async def test_learn_raises_existing_level(graph):
    await make_user()
    await progress.learn("maya", {"react": "framework"})
    react = next(s for s in (await progress.get_user("maya")).skills if s.tech == "react")
    assert react.level == 0.5


async def test_attempt_lifecycle_and_sync_dedupe(graph):
    await make_user()
    attempt = await progress.start_attempt("maya", ISSUE, "Fix the widget", "https://github.com/acme/widgets/issues/42", "acme/widgets")
    assert attempt.status == "selected"

    synced = [
        Event(type="commit", at=T0, gh_id="abc123"),
        Event(type="pr_opened", at=T0 + timedelta(hours=2), gh_id="pr-7", url="https://github.com/acme/widgets/pull/7"),
        Event(type="changes_requested", at=T0 + timedelta(days=1), gh_id="review-1"),
    ]
    new = await progress.append_events(attempt.id, synced)
    assert len(new) == 3

    # Syncing the same GitHub activity again adds nothing.
    assert await progress.append_events(attempt.id, synced) == []

    attempt = await progress.get_attempt(attempt.id)
    assert attempt.status == "changes_requested"
    assert attempt.pr_url == "https://github.com/acme/widgets/pull/7"
    assert [e.type for e in attempt.events][1:] == ["commit", "pr_opened", "changes_requested"]

    await progress.append_events(attempt.id, [Event(type="commit", at=T0 + timedelta(days=2), gh_id="def456")])
    assert (await progress.get_attempt(attempt.id)).status == "in_review"


async def test_picking_same_issue_twice_reuses_attempt(graph):
    await make_user()
    a1 = await progress.start_attempt("maya", ISSUE, "t", "u", "acme/widgets")
    a2 = await progress.start_attempt("maya", ISSUE, "t", "u", "acme/widgets")
    assert a1.id == a2.id
    assert len(await progress.list_attempts("maya")) == 1
    assert len(a2.events) == 1


async def test_seen_issues_include_skipped_and_attempted(graph):
    await make_user()
    await progress.skip_issue("maya", "acme/widgets#1", "too_hard")
    await progress.start_attempt("maya", ISSUE, "t", "u", "acme/widgets")
    assert await progress.seen_issue_ids("maya") == {"acme/widgets#1", ISSUE}
