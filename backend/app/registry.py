"""Resolve packages ("npm:react", "pypi:fastapi") to their GitHub repos, for B3.

Uses the npm and PyPI registries, not the GitHub API, so it costs no GitHub
rate limit. Results are cached for a week: a package's repo rarely moves.
"""

import re

import httpx

from app.cache import Cache
from app.config import get_settings
from app.db import get_redis

_GITHUB_REPO = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$")

WEEK = 7 * 24 * 60 * 60

# Mock mode: a few well-known packages, so B3 works offline.
MOCK_REPOS = {
    "npm:react": "facebook/react",
    "npm:next": "vercel/next.js",
    "npm:jest": "jestjs/jest",
    "npm:vitest": "vitest-dev/vitest",
    "npm:@testing-library/react": "testing-library/react-testing-library",
    "npm:web-vitals": "GoogleChrome/web-vitals",
    "pypi:fastapi": "fastapi/fastapi",
    "pypi:pytest": "pytest-dev/pytest",
    "pypi:django": "django/django",
}


def github_repo_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = _GITHUB_REPO.search(url.strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _repo_from_npm(data: dict) -> str | None:
    repo = data.get("repository")
    url = repo.get("url") if isinstance(repo, dict) else repo
    return github_repo_from_url(url) or github_repo_from_url(data.get("homepage"))


def _repo_from_pypi(data: dict) -> str | None:
    info = data.get("info", {})
    urls = info.get("project_urls") or {}
    # Prefer explicit source links over the homepage.
    for key in ("Source", "Source Code", "Repository", "Code", "GitHub", "Homepage"):
        if repo := github_repo_from_url(urls.get(key)):
            return repo
    for url in [*urls.values(), info.get("home_page")]:
        if repo := github_repo_from_url(url):
            return repo
    return None


class Registry:
    def __init__(self, cache: Cache | None):
        self.cache = cache
        self.http = httpx.AsyncClient(timeout=10, follow_redirects=True)

    async def repo_for(self, package: str) -> str | None:
        if self.cache is None:
            return MOCK_REPOS.get(package)

        key = f"registry:{package}"
        if (hit := await self.cache.get(key)) is not None:
            return hit or None  # "" caches "no GitHub repo"

        ecosystem, name = package.split(":", 1)
        try:
            if ecosystem == "npm":
                resp = await self.http.get(f"https://registry.npmjs.org/{name}/latest")
                repo = _repo_from_npm(resp.json()) if resp.is_success else None
            elif ecosystem == "pypi":
                resp = await self.http.get(f"https://pypi.org/pypi/{name}/json")
                repo = _repo_from_pypi(resp.json()) if resp.is_success else None
            else:
                repo = None
        except (httpx.HTTPError, ValueError):
            return None  # don't cache failures; try again next time

        await self.cache.set(key, repo or "", ttl=WEEK)
        return repo


_registry: Registry | None = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        s = get_settings()
        live = s.service_mode("github") == "live"
        _registry = Registry(Cache(get_redis(), stale_ttl=s.ttl_stale) if live else None)
    return _registry
