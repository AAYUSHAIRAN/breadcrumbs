from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_redis
from app.graph.schema import ensure_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema()
    yield


app = FastAPI(title="Breadcrumbs API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    return {
        "ok": await get_redis().ping(),
        "mode": s.mode,
        "services": {"github": s.service_mode("github"), "llm": s.service_mode("llm")},
    }
