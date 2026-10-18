from fastapi import APIRouter, HTTPException

from app.contracts import Fingerprint
from app.fingerprint.builder import UserNotFound, fingerprint
from app.github import get_github
from app.graph import progress

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
