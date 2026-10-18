"""Runtime configuration.

MODE=mock (default) runs fully offline on fixtures. MODE=live uses real APIs,
but each service falls back to mock on its own if its key is missing, so one
dead key costs one feature, never the whole demo.
"""

import logging
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

Mode = Literal["mock", "live"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    mode: Mode = "mock"

    github_token: str = ""
    github_api_url: str = "https://api.github.com"

    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    graph_name: str = "breadcrumbs"

    # Cache TTLs (seconds). Stale copies are kept longer as a fallback when GitHub fails.
    ttl_search: int = 15 * 60
    ttl_repo_stats: int = 24 * 60 * 60
    ttl_stale: int = 7 * 24 * 60 * 60

    def service_mode(self, service: Literal["github", "llm"]) -> Mode:
        if self.mode == "mock":
            return "mock"
        key = {"github": self.github_token, "llm": self.llm_api_key}[service]
        if not key:
            log.warning("MODE=live but no key for %s; using mock for it", service)
            return "mock"
        return "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
