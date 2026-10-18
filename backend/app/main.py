import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_redis
from app.github import reset_stale
from app.graph.schema import ensure_schema
from app.routes import users

log = logging.getLogger("breadcrumbs")
SCHEMA_ATTEMPTS = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On hosts like Railway the database can come up (or become reachable) a few
    # seconds after the API. Retry instead of crashing; start serving either way.
    for attempt in range(1, SCHEMA_ATTEMPTS + 1):
        try:
            await ensure_schema()
            break
        except Exception as e:  # noqa: BLE001 - any connection error: log and retry
            log.warning("FalkorDB not ready (attempt %d/%d): %s", attempt, SCHEMA_ATTEMPTS, e)
            await asyncio.sleep(3)
    yield


app = FastAPI(title="Breadcrumbs API", lifespan=lifespan)
# Local dev, plus the deployed frontend on Vercel.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://[\w-]+\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(users.router)


@app.middleware("http")
async def stale_flag(request: Request, call_next):
    reset_stale()
    return await call_next(request)


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    try:
        db_ok = await get_redis().ping()
    except Exception as e:  # noqa: BLE001 - report, don't crash, so deploys can be debugged
        db_ok, s_err = False, str(e)
    else:
        s_err = None
    return {
        "ok": db_ok,
        "db_error": s_err,
        "mode": s.mode,
        "services": {"github": s.service_mode("github"), "llm": s.service_mode("llm")},
    }
