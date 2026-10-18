import pytest

from app.cache import Cache
from app.db import get_redis
from app.github import GitHubError, LiveGitHub, served_stale


class FailingLive(LiveGitHub):
    """LiveGitHub whose network always fails, to test the stale fallback."""

    def __init__(self, cache):
        super().__init__(token="x", api_url="https://example.invalid", cache=cache, default_ttl=60)


async def test_falls_back_to_stale_copy_when_github_fails():
    redis = get_redis()
    cache = Cache(redis, stale_ttl=60)
    gh = FailingLive(cache)

    async def boom():
        raise GitHubError("down")

    async def ok():
        return {"v": 1}

    key = "gh:test:stale"
    await redis.delete("cache:" + key, "stale:" + key)

    assert await gh._cached(key, 60, ok) == {"v": 1}
    await redis.delete("cache:" + key)  # fresh copy expired

    served_stale.set(False)
    assert await gh._cached(key, 60, boom) == {"v": 1}
    assert served_stale.get() is True


async def test_no_stale_copy_raises():
    gh = FailingLive(Cache(get_redis(), stale_ttl=60))

    async def boom():
        raise GitHubError("down")

    with pytest.raises(GitHubError):
        await gh._cached("gh:test:never-cached", 60, boom)
