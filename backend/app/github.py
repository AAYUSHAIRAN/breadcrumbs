"""GitHub access: live HTTP client with a TTL cache, or offline fixtures.

Use `get_github()`; never construct clients directly. If a live call fails
(rate limit, outage), we serve the last stale copy and mark the request with
`served_stale`, so the API can tell the UI that data may be outdated (G7).
"""

import contextvars
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.cache import Cache
from app.config import get_settings
from app.db import get_redis

FIXTURES = Path(__file__).parent.parent / "fixtures" / "github"

served_stale: contextvars.ContextVar[bool] = contextvars.ContextVar("served_stale", default=False)


class GitHubError(Exception):
    pass


class RateLimited(GitHubError):
    pass


class GitHub(Protocol):
    async def rest(self, path: str, params: dict | None = None, ttl: int | None = None) -> Any: ...
    async def graphql(self, query: str, variables: dict | None = None, ttl: int | None = None) -> Any: ...
    async def raw_file(self, owner: str, repo: str, ref: str, path: str) -> str: ...


def _key(*parts: Any) -> str:
    digest = hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]
    return f"gh:{parts[0]}:{digest}"


def _operation_name(query: str) -> str:
    match = re.search(r"\b(?:query|mutation)\s+(\w+)", query)
    if not match:
        raise GitHubError("GraphQL queries must be named, e.g. `query UserRepos(...)`")
    return match.group(1)


class LiveGitHub:
    def __init__(self, token: str, api_url: str, cache: Cache, default_ttl: int):
        self.cache = cache
        self.default_ttl = default_ttl
        self.http = httpx.AsyncClient(
            base_url=api_url,
            timeout=20,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        self.raw = httpx.AsyncClient(base_url="https://raw.githubusercontent.com", timeout=20)

    async def _cached(self, key: str, ttl: int, fetch) -> Any:
        if (hit := await self.cache.get(key)) is not None:
            return hit
        try:
            value = await fetch()
        except (GitHubError, httpx.HTTPError):
            if (stale := await self.cache.get_stale(key)) is not None:
                served_stale.set(True)
                return stale
            raise
        await self.cache.set(key, value, ttl)
        return value

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        limited = resp.status_code == 429 or (
            resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0"
        )
        if limited:
            raise RateLimited(f"GitHub rate limit hit; resets at {resp.headers.get('x-ratelimit-reset')}")
        if resp.is_error:
            raise GitHubError(f"GitHub {resp.status_code}: {resp.text[:200]}")

    async def rest(self, path: str, params: dict | None = None, ttl: int | None = None) -> Any:
        async def fetch():
            resp = await self.http.get(path, params=params)
            self._check(resp)
            return resp.json()

        return await self._cached(_key("rest", path, params), ttl or self.default_ttl, fetch)

    async def graphql(self, query: str, variables: dict | None = None, ttl: int | None = None) -> Any:
        async def fetch():
            resp = await self.http.post("/graphql", json={"query": query, "variables": variables or {}})
            self._check(resp)
            body = resp.json()
            if body.get("errors"):
                raise GitHubError(f"GraphQL: {body['errors'][0].get('message')}")
            return body["data"]

        key = _key("graphql", _operation_name(query), variables)
        return await self._cached(key, ttl or self.default_ttl, fetch)

    async def raw_file(self, owner: str, repo: str, ref: str, path: str) -> str:
        # Keyed by commit SHA, so content never changes: cache for the stale TTL.
        async def fetch():
            resp = await self.raw.get(f"/{owner}/{repo}/{ref}/{path}")
            self._check(resp)
            return resp.text

        return await self._cached(_key("raw", owner, repo, ref, path), self.cache.stale_ttl, fetch)


class MockGitHub:
    """Serves JSON fixtures from backend/fixtures/github/.

    rest("/users/octocat/repos") → rest/users__octocat__repos.json
    graphql("query UserPRs ...") → graphql/UserPRs.json
    raw_file(o, r, ref, "src/a.ts") → raw/o__r__src__a.ts
    """

    def _load(self, relative: str) -> str:
        path = FIXTURES / relative
        if not path.exists():
            raise GitHubError(f"Mock fixture missing: fixtures/github/{relative}")
        return path.read_text()

    async def rest(self, path: str, params: dict | None = None, ttl: int | None = None) -> Any:
        return json.loads(self._load(f"rest/{path.strip('/').replace('/', '__')}.json"))

    async def graphql(self, query: str, variables: dict | None = None, ttl: int | None = None) -> Any:
        return json.loads(self._load(f"graphql/{_operation_name(query)}.json"))

    async def raw_file(self, owner: str, repo: str, ref: str, path: str) -> str:
        return self._load(f"raw/{owner}__{repo}__{path.replace('/', '__')}")


_client: GitHub | None = None


def get_github() -> GitHub:
    global _client
    if _client is None:
        s = get_settings()
        if s.service_mode("github") == "live":
            cache = Cache(get_redis(), stale_ttl=s.ttl_stale)
            _client = LiveGitHub(s.github_token, s.github_api_url, cache, default_ttl=s.ttl_search)
        else:
            _client = MockGitHub()
    return _client
