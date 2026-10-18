from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.contracts import Attempt, Fingerprint, Matches, SkipRequest
from app.discovery import availability
from app.discovery.matches import find_matches
from app.discovery.search import Candidate, find_candidates
from app.fingerprint.builder import UserNotFound, fingerprint
from app.github import get_github, is_stale
from app.graph import progress
from app.registry import get_registry

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{login}/fingerprint")
async def get_fingerprint(login: str) -> Fingerprint:
    """A1: build the user's skill fingerprint from GitHub and save it to their progress."""
    try:
        fp = await fingerprint(get_github(), login)
    except UserNotFound:
        raise HTTPException(404, f"GitHub user {login!r} not found") from None
    await progress.upsert_user(fp)
    return await progress.get_user(fp.login) or fp


class Candidates(BaseModel):
    login: str
    candidates: list[Candidate]
    stale: bool


@router.get("/{login}/candidates")
async def get_candidates(login: str) -> Candidates:
    """B1/B3 raw candidates, before checking and ranking (T1.4 turns these into /matches)."""
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
    return Matches(login=fp.login, issues=cards, stale=is_stale())


@router.post("/{login}/issues/{owner}/{repo}/{number}/skip", status_code=204)
async def skip(login: str, owner: str, repo: str, number: int, body: SkipRequest) -> None:
    """B6: hide an issue from future matches, remembering why."""
    if not await progress.get_user(login):
        raise HTTPException(404, f"unknown user {login!r}; fetch their fingerprint first")
    await progress.skip_issue(login, f"{owner}/{repo}#{number}", body.reason)


class PickRequest(BaseModel):
    issue_id: str  # "owner/repo#number"
    force: bool = False  # pick even if the re-check says it's taken


@router.post("/{login}/attempts", status_code=201)
async def pick(login: str, body: PickRequest) -> Attempt:
    """C1 + C3: re-check the issue on live GitHub, then start an attempt.

    409 with the reason if it was taken since the user saw it, unless force=true.
    """
    if not await progress.get_user(login):
        raise HTTPException(404, f"unknown user {login!r}; fetch their fingerprint first")
    try:
        status = await availability.check(get_github(), body.issue_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    if status.reason == "not_found" or (not status.available and not body.force):
        raise HTTPException(409 if status.reason != "not_found" else 404, status.model_dump())

    owner, name, _ = availability.parse_issue_id(body.issue_id)
    return await progress.start_attempt(login, body.issue_id, status.title, status.url, f"{owner}/{name}")
