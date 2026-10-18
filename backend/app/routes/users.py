from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent import guide as guide_agent
from app.agent import memory as agent_memory
from app.contracts import Attempt, Fingerprint, GraphView, IssueCard, IssueDetail, Matches, Preferences, SkipRequest
from app.discovery import availability
from app.discovery.detail import IssueNotFound, issue_detail
from app.discovery.matches import find_matches
from app.discovery.search import Candidate, find_candidates
from app.fingerprint.builder import UserNotFound, fingerprint
from app.github import get_github, is_stale
from app.graph import progress, views
from app.registry import get_registry

router = APIRouter(prefix="/users", tags=["users"])


async def _user(login: str) -> Fingerprint:
    """A user we already know, or 404. Call /fingerprint first to create one."""
    if fp := await progress.get_user(login):
        return fp
    raise HTTPException(404, f"unknown user {login!r}; fetch their fingerprint first")


def _issue_id(owner: str, repo: str, number: int) -> str:
    return f"{owner}/{repo}#{number}"


# --- Onboarding --------------------------------------------------------------------


@router.get("/{login}/fingerprint")
async def get_fingerprint(login: str) -> Fingerprint:
    """A1: build the user's skill fingerprint from GitHub and save it to their progress."""
    try:
        fp = await fingerprint(get_github(), login)
    except UserNotFound:
        raise HTTPException(404, f"GitHub user {login!r} not found") from None
    await progress.upsert_user(fp)
    return await progress.get_user(fp.login) or fp


@router.put("/{login}/preferences")
async def put_preferences(login: str, prefs: Preferences) -> Fingerprint:
    """A5: languages to search, difficulty, hours per week."""
    fp = await _user(login)
    await progress.set_preferences(fp.login, prefs)
    return await _user(fp.login)


# --- Discovery ------------------------------------------------------------------------


class Candidates(BaseModel):
    login: str
    candidates: list[Candidate]
    stale: bool


@router.get("/{login}/candidates")
async def get_candidates(login: str) -> Candidates:
    """B1/B3 raw candidates, before checking and ranking (debugging; the UI uses /matches)."""
    fp = await progress.get_user(login) or await get_fingerprint(login)
    seen = await progress.seen_issue_ids(fp.login)
    candidates = await find_candidates(get_github(), get_registry(), fp, seen)
    return Candidates(login=fp.login, candidates=candidates, stale=is_stale())


@router.get("/{login}/matches")
async def get_matches(login: str) -> Matches:
    """B1: ranked issue cards with why-chips, skipping issues the user has skipped or started."""
    fp = await progress.get_user(login) or await get_fingerprint(login)
    seen = await progress.seen_issue_ids(fp.login)
    cards = await find_matches(get_github(), get_registry(), fp, seen)
    await progress.record_shown(fp.login, cards)
    saved = {c.id for c in await progress.saved_issues(fp.login)}
    cards = [c.model_copy(update={"saved": c.id in saved}) for c in cards]
    return Matches(login=fp.login, issues=cards, stale=is_stale())


@router.get("/{login}/issues/{owner}/{repo}/{number}")
async def get_issue(login: str, owner: str, repo: str, number: int) -> IssueDetail:
    """B5 (and B4): any issue, scored for this user."""
    fp = await _user(login)
    issue_id = _issue_id(owner, repo, number)
    try:
        detail = await issue_detail(get_github(), get_registry(), fp, issue_id)
    except IssueNotFound:
        raise HTTPException(404, f"issue {issue_id} not found") from None
    await progress.record_shown(fp.login, [detail.card])
    saved = {c.id for c in await progress.saved_issues(fp.login)}
    attempt = await progress.get_attempt(progress.attempt_id(fp.login, detail.card.id))
    return detail.model_copy(
        update={
            "card": detail.card.model_copy(update={"saved": detail.card.id in saved}),
            "attempt_id": attempt.id if attempt else None,
            "stale": is_stale(),
        }
    )


@router.get("/{login}/issues/{owner}/{repo}/{number}/why")
async def get_why(login: str, owner: str, repo: str, number: int) -> GraphView:
    """The graph path behind a match: You → Tech ← Issue → Repo (+ repo facts, past work there)."""
    view = await views.why_path(login, _issue_id(owner, repo, number))
    if not view:
        raise HTTPException(404, "not in your graph yet; open the issue first")
    return view


@router.post("/{login}/issues/{owner}/{repo}/{number}/skip", status_code=204)
async def skip(login: str, owner: str, repo: str, number: int, body: SkipRequest) -> None:
    """B6: hide an issue from future matches, remembering why."""
    await _user(login)
    await progress.skip_issue(login, _issue_id(owner, repo, number), body.reason)


@router.post("/{login}/saved", status_code=204)
async def save(login: str, card: IssueCard) -> None:
    """B7: save an issue for later."""
    await _user(login)
    await progress.save_issue(login, card)


@router.delete("/{login}/saved/{owner}/{repo}/{number}", status_code=204)
async def unsave(login: str, owner: str, repo: str, number: int) -> None:
    await progress.unsave_issue(login, _issue_id(owner, repo, number))


@router.get("/{login}/saved")
async def list_saved(login: str) -> list[IssueCard]:
    return await progress.saved_issues(login)


# --- Attempts --------------------------------------------------------------------------


class PickRequest(BaseModel):
    issue_id: str  # "owner/repo#number"
    force: bool = False  # pick even if the re-check says it's taken


@router.post("/{login}/attempts", status_code=201)
async def pick(login: str, body: PickRequest) -> Attempt:
    """C1 + C3: re-check the issue on live GitHub, then start an attempt.

    409 with the reason if it was taken since the user saw it, unless force=true.
    """
    await _user(login)
    try:
        status = await availability.check(get_github(), body.issue_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    if status.reason == "not_found" or (not status.available and not body.force):
        raise HTTPException(409 if status.reason != "not_found" else 404, status.model_dump())

    owner, name, _ = availability.parse_issue_id(body.issue_id)
    return await progress.start_attempt(login, body.issue_id, status.title, status.url, f"{owner}/{name}")


@router.get("/{login}/attempts")
async def list_attempts(login: str) -> list[Attempt]:
    """The user's attempts, most recently active first."""
    return await progress.list_attempts(login)


@router.get("/{login}/attempts/{owner}/{repo}/{number}")
async def get_attempt(login: str, owner: str, repo: str, number: int) -> Attempt:
    attempt = await progress.get_attempt(progress.attempt_id(login, _issue_id(owner, repo, number)))
    if not attempt:
        raise HTTPException(404, "no attempt for that issue")
    return attempt


# --- Graph -------------------------------------------------------------------------------


@router.get("/{login}/graph")
async def get_trail_graph(login: str) -> GraphView:
    """F3: the user's trail as a graph: skills, attempts, repos, what they learned."""
    view = await views.trail_graph(login)
    if not view:
        raise HTTPException(404, f"unknown user {login!r}")
    return view


# --- Guide agent ----------------------------------------------------------------


@router.get("/{login}/attempts/{owner}/{repo}/{number}/guide")
async def get_guide(login: str, owner: str, repo: str, number: int) -> dict:
    """The last drafts the Guide wrote for this attempt, or {} if none yet."""
    return await guide_agent.saved_guide(progress.attempt_id(login, _issue_id(owner, repo, number))) or {}


@router.post("/{login}/attempts/{owner}/{repo}/{number}/guide")
async def write_guide(login: str, owner: str, repo: str, number: int) -> dict:
    """Run the Guide agent: read the repo's rules and the user's graph, write drafts, remember what it learned."""
    await _user(login)
    try:
        return await guide_agent.write_guide(get_github(), login, _issue_id(owner, repo, number))
    except KeyError:
        raise HTTPException(404, "no attempt for that issue") from None
    except guide_agent.GuideUnavailable as e:
        raise HTTPException(503, str(e)) from None


@router.get("/{login}/memory")
async def get_memory(login: str) -> dict:
    """What the agents remember about this user."""
    return {"memories": await agent_memory.memories(login)}


@router.delete("/{login}/memory/{memory_id}", status_code=204)
async def delete_memory(login: str, memory_id: str) -> None:
    await agent_memory.forget(login, memory_id)



@router.get("/{login}/repo-facts/{owner}/{repo}")
async def get_repo_facts(login: str, owner: str, repo: str) -> list[dict]:
    """What Breadcrumbs has learned about a repo, from every user's Guide runs."""
    return await guide_agent.repo_facts(f"{owner}/{repo}")
