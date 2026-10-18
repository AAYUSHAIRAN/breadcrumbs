from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_redis
from app.github import reset_stale
from app.graph.schema import ensure_schema
from app.routes import users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema()
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
    return {
        "ok": await get_redis().ping(),
        "mode": s.mode,
        "services": {"github": s.service_mode("github"), "llm": s.service_mode("llm")},
    }
