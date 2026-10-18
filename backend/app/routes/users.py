from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.contracts import Fingerprint
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
