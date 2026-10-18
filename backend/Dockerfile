# Breadcrumbs API. Runs anywhere Docker does (Railway, Render, Fly).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY fixtures ./fixtures

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
# Hosts set PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
