"""Turn checked candidates into ranked issue cards (B1, B5, F2c).

    fit = 0.35 × skill        how well the user knows the repo's language or library
        + 0.20 × difficulty   closeness to one step above the user's level
        + 0.20 × maintainer   1 / (1 + reply_hours / 24); unknown counts as 0.4
        + 0.15 × newcomers    1 − e^(−merges_90d / 3)
        + 0.10 × freshness    halves every 30 days since the last update
        (+0.05 if it's in a library the user depends on; ×0.3 if claimed)

    merge_forecast = newcomer merge rate (with a prior of 1 merged in 2)
                   × (0.6 + 0.4 × difficulty) × (0.5 + 0.5 × maintainer)
                   × 0.3 if claimed

Both are heuristics for ordering and for a rough "chance" ring, not
calibrated probabilities.
"""

import math
from datetime import datetime, timedelta

from app.contracts import Difficulty, Fingerprint, IssueCard, Level, WhyChip
from app.discovery.checks import Claim, RepoStats
from app.discovery.search import Candidate
from app.fingerprint.deps import KNOWN

WEIGHTS = {"skill": 0.35, "difficulty": 0.20, "maintainer": 0.20, "newcomers": 0.15, "freshness": 0.10}
DEPENDENCY_BONUS = 0.05
CLAIMED_PENALTY = 0.3
UNKNOWN_MAINTAINER = 0.4
DEPENDENCY_SKILL_FLOOR = 0.6  # you use the library, so you know it at least this well

EASY_LABELS = ("good first issue", "good-first-issue", "first-timers-only", "beginner", "easy", "starter")
HARD_LABELS = ("hard", "complex", "advanced", "difficult", "breaking", "performance", "security", "architecture")
DIFFICULTIES: list[Difficulty] = ["easy", "medium", "hard"]
TARGET: dict[Level, Difficulty] = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}
LONG_BODY = 2000
OLD_CLAIM_SHOWN = timedelta(days=90)  # older expired claims are just noise


def difficulty(labels: list[str], body: str) -> Difficulty:
    names = [label.lower() for label in labels]
    if any(h in name for name in names for h in HARD_LABELS):
        return "hard"
    if any(e in name for name in names for e in EASY_LABELS):
        return "medium" if len(body) >= LONG_BODY else "easy"
    return "medium"


def difficulty_fit(issue: Difficulty, level: Level) -> float:
    gap = abs(DIFFICULTIES.index(issue) - DIFFICULTIES.index(TARGET[level]))
    return 1 - 0.5 * gap


def skill_score(c: Candidate, fp: Fingerprint) -> tuple[float, str]:
    """(score, tech name) for the skill this issue draws on."""
    levels = {s.tech: s.level for s in fp.skills}
    if c.source == "dependency":
        tech = KNOWN.get(c.matched, (c.matched.split(":", 1)[-1], ""))[0]
        return max(levels.get(tech, 0), DEPENDENCY_SKILL_FLOOR), tech
    return levels.get(c.matched, 0), c.matched


def maintainer_score(stats: RepoStats | None) -> float:
    if not stats or stats.reply_hours is None:
        return UNKNOWN_MAINTAINER
    return 1 / (1 + stats.reply_hours / 24)


def newcomer_score(stats: RepoStats | None) -> float:
    return 1 - math.exp(-(stats.newcomer_merges_90d if stats else 0) / 3)


def freshness(updated_at: datetime, now: datetime) -> float:
    return 0.5 ** (max((now - updated_at).days, 0) / 30)


def _hours(h: float) -> str:
    if h < 1:
        return "under an hour"
    if h < 48:
        return f"{round(h)}h"
    return f"{round(h / 24)} days"


def _ago(at: datetime, now: datetime) -> str:
    days = (now - at).days
    return "today" if days == 0 else f"{days} day{'s' if days != 1 else ''} ago"


def why_chips(
    c: Candidate, fp: Fingerprint, stats: RepoStats | None, claim: Claim, diff: Difficulty, tech: str, now: datetime
) -> list[WhyChip]:
    chips: list[WhyChip] = []
    if c.source == "dependency":
        chips.append(WhyChip(kind="dependency", label=f"📦 in {tech}, which your projects use"))
    elif tech and tech != "any":
        chips.append(WhyChip(kind="skill", label=f"uses your {tech}"))

    if claim.claimed:
        chips.append(WhyChip(kind="warning", label=f"@{claim.by} asked to work on this {_ago(claim.at, now)}"))
    elif claim.expired and now - claim.at <= OLD_CLAIM_SHOWN:
        chips.append(WhyChip(kind="unclaimed", label=f"@{claim.by} asked {_ago(claim.at, now)}, no PR since"))
    else:
        chips.append(WhyChip(kind="unclaimed", label="nobody's claimed it"))

    if stats and stats.reply_hours is not None:
        if stats.reply_hours <= 48:
            chips.append(WhyChip(kind="fast_maintainer", label=f"maintainers usually reply within {_hours(stats.reply_hours)}"))
        elif stats.reply_hours > 7 * 24:
            chips.append(WhyChip(kind="warning", label=f"maintainers are slow to reply (~{_hours(stats.reply_hours)})"))

    if stats and stats.newcomer_merges_90d:
        n = stats.newcomer_merges_90d
        chips.append(WhyChip(kind="newcomers", label=f"{n} newcomer PR{'s' if n != 1 else ''} merged here in 90 days"))

    if diff == "easy":
        chips.append(WhyChip(kind="small_scope", label="labelled as a good first issue"))
    if c.comments > 15:
        chips.append(WhyChip(kind="warning", label=f"long discussion ({c.comments} comments)"))
    return chips


def score(c: Candidate, fp: Fingerprint, stats: RepoStats | None, claim: Claim, now: datetime) -> IssueCard:
    diff = difficulty(c.labels, c.body)
    skill, tech = skill_score(c, fp)
    parts = {
        "skill": skill,
        "difficulty": difficulty_fit(diff, fp.level),
        "maintainer": maintainer_score(stats),
        "newcomers": newcomer_score(stats),
        "freshness": freshness(c.updated_at, now),
    }
    fit = sum(WEIGHTS[k] * v for k, v in parts.items())
    if c.source == "dependency":
        fit += DEPENDENCY_BONUS
    if claim.claimed:
        fit *= CLAIMED_PENALTY

    merged, closed = (stats.newcomer_merged, stats.newcomer_closed) if stats else (0, 0)
    merge_rate = (merged + 1) / (merged + closed + 2)
    forecast = merge_rate * (0.6 + 0.4 * parts["difficulty"]) * (0.5 + 0.5 * parts["maintainer"])
    if claim.claimed:
        forecast *= CLAIMED_PENALTY

    return IssueCard(
        id=c.id,
        url=c.url,
        repo=c.repo,
        repo_stars=c.repo_stars,
        number=c.number,
        title=c.title,
        labels=c.labels,
        updated_at=c.updated_at,
        difficulty=diff,
        fit=round(min(fit, 1), 3),
        merge_forecast=round(min(forecast, 1), 3),
        claimed=claim.claimed,
        maintainer_reply_hours=stats.reply_hours if stats else None,
        newcomer_merges_90d=stats.newcomer_merges_90d if stats else 0,
        in_dependencies=c.source == "dependency",
        why=why_chips(c, fp, stats, claim, diff, tech, now),
    )


def prerank(c: Candidate, fp: Fingerprint, now: datetime) -> float:
    """Cheap score before any checks, to decide which candidates are worth checking."""
    skill, _ = skill_score(c, fp)
    return (
        WEIGHTS["skill"] * skill
        + WEIGHTS["difficulty"] * difficulty_fit(difficulty(c.labels, c.body), fp.level)
        + WEIGHTS["freshness"] * freshness(c.updated_at, now)
        + (DEPENDENCY_BONUS if c.source == "dependency" else 0)
    )
