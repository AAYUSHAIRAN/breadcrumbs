"""API contracts. Mirror any change in frontend/src/lib/contracts.ts.

Issue IDs are "owner/repo#number" everywhere.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced"]
Difficulty = Literal["easy", "medium", "hard"]

AttemptStatus = Literal[
    "selected",
    "in_progress",
    "pr_open",
    "in_review",
    "changes_requested",
    "merged",
    "closed",
    "abandoned",
]

EventType = Literal[
    "selected",
    "commit",
    "pr_opened",
    "review_commented",
    "changes_requested",
    "approved",
    "merged",
    "pr_closed",
    "issue_closed",
    "abandoned",
]


# --- Onboarding --------------------------------------------------------------


class Skill(BaseModel):
    tech: str  # e.g. "typescript", "react", "pytest"
    kind: Literal["language", "framework", "library", "tool"]
    level: float = Field(ge=0, le=1)
    source: Literal["inferred", "manual", "learned"] = "inferred"


class Fingerprint(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str | None = None
    level: Level
    skills: list[Skill]
    merged_prs: int = 0
    dependencies: list[str] = []  # packages from dependency files, e.g. "npm:react", "pypi:fastapi"


# --- Discovery ---------------------------------------------------------------


class WhyChip(BaseModel):
    kind: Literal[
        "skill",
        "unclaimed",
        "fast_maintainer",
        "first_timers",
        "small_scope",
        "dependency",
        "warning",
    ]
    label: str  # plain language, e.g. "matches your React + Jest"


class IssueCard(BaseModel):
    id: str
    url: str
    repo: str
    number: int
    title: str
    labels: list[str]
    updated_at: datetime
    difficulty: Difficulty
    fit: float = Field(ge=0, le=1)
    merge_forecast: float = Field(ge=0, le=1)
    claimed: bool
    maintainer_reply_hours: float | None = None
    first_timer_merges_90d: int = 0
    in_dependencies: bool = False
    why: list[WhyChip]


class Matches(BaseModel):
    login: str
    issues: list[IssueCard]
    stale: bool = False  # true if any GitHub data came from the fallback cache


class SkipRequest(BaseModel):
    reason: Literal["not_interested", "too_hard", "too_easy", "wrong_tech", "other"] = "not_interested"


# --- Attempts and progress ---------------------------------------------------


class Event(BaseModel):
    type: EventType
    at: datetime
    gh_id: str | None = None  # commit SHA, PR number, review ID: used to dedupe syncs
    url: str | None = None
    summary: str = ""


class Attempt(BaseModel):
    id: str
    issue_id: str
    issue_title: str
    issue_url: str
    status: AttemptStatus
    started_at: datetime
    last_activity_at: datetime
    pr_url: str | None = None
    events: list[Event] = []


class Nudge(BaseModel):
    attempt_id: str
    kind: Literal["quiet", "review_waiting", "changes_requested"]
    message: str


class Dashboard(BaseModel):
    user: Fingerprint
    active: list[Attempt]
    finished: list[Attempt]
    nudges: list[Nudge]
    stale: bool = False


# --- Guidance ----------------------------------------------------------------


class ReadingStep(BaseModel):
    order: int
    file: str
    symbol: str | None = None
    role: Literal["entry", "step", "target", "test"]
    url: str
    why: str = ""


class CodeNode(BaseModel):
    id: str  # "path/to/file.ts#symbol" or "path/to/file.ts"
    kind: Literal["file", "function", "class", "test"]
    label: str


class CodeEdge(BaseModel):
    source: str
    target: str
    kind: Literal["contains", "calls", "imports", "tested_by"]


class ReadingPath(BaseModel):
    issue_id: str
    commit_sha: str
    steps: list[ReadingStep]
    nodes: list[CodeNode]
    edges: list[CodeEdge]


class Precedent(BaseModel):
    pr_url: str
    title: str
    author: str
    first_time: bool
    reviewer: str | None = None
    reply_hours: float | None = None
    merged_at: datetime
    shared_files: list[str]


class Draft(BaseModel):
    kind: Literal["claim_comment", "setup", "pr_description", "review_explainer"]
    text: str
    sources: list[str] = []  # files the draft is based on, e.g. CONTRIBUTING.md
