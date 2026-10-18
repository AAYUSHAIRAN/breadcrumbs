"""Guide agent: personalised claim comment, setup steps and PR description for one attempt.

1. Reads the repo's own rules from GitHub in one GraphQL call (CONTRIBUTING, PR template,
   README, CI workflow, package scripts).
2. Pulls context from the graph: the user's skills, level, preferences and remembered facts,
   and what earlier runs already learned about this repo (shared across users).
3. Asks Claude for drafts that follow those rules, citing the file each comes from.
4. Writes what it learned back to the graph: facts about the repo on the Repo node (so the
   next newcomer starts with them) and facts about the user on the User node.
"""

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
from datetime import UTC, datetime

import anthropic
from pydantic import BaseModel, Field

from app.agent import memory
from app.config import get_settings
from app.discovery.availability import parse_issue_id
from app.github import GitHub, GitHubError
from app.graph import progress
from app.graph.progress import _rows

MODEL = "claude-opus-5"
MAX_FILE_CHARS = 6000
MAX_FACTS = 3  # memory notes saved per run, per kind

# Where repos keep their rules. One GraphQL call fetches all of them.
FILES = {
    "contributing": ["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md", "CONTRIBUTING.rst"],
    "pr_template": [".github/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md", "PULL_REQUEST_TEMPLATE.md"],
    "readme": ["README.md", "README.rst"],
    "package_json": ["package.json"],
    "pyproject": ["pyproject.toml"],
    "makefile": ["Makefile"],
}


class Step(BaseModel):
    command: str = Field(description="A shell command, exactly as the user should run it")
    why: str = Field(description="What it does, in a few words")


class Fact(BaseModel):
    fact: str = Field(description="One short, durable fact")
    source: str = Field(description="The file it came from, e.g. CONTRIBUTING.md, or 'profile'")


class GuideOut(BaseModel):
    claim_comment: str = Field(description="A short, friendly comment for the issue asking to work on it, following the repo's rules")
    setup_steps: list[Step] = Field(description="Fork, clone, install, run tests: using the repo's real commands")
    pr_title: str = Field(description="A PR title in the repo's convention")
    pr_description: str = Field(description="A PR description following the repo's PR template if it has one, with 'Fixes #N'")
    tips: list[str] = Field(description="2-4 tips specific to this user and repo, e.g. what to read first given their skills")
    learned_about_repo: list[Fact] = Field(description="Durable facts about how this repo works (package manager, test command, PR rules, CLA, branch naming)")
    learned_about_user: list[Fact] = Field(description="Durable facts about the user worth remembering for next time; often empty")


class GuideUnavailable(Exception):
    pass


CLI_TIMEOUT_S = 240


def provider() -> str | None:
    """"api" with LLM_API_KEY; else "cli" if the local Claude Code CLI is installed (runs on
    your Claude subscription, for local demos); None in mock mode or with neither."""
    s = get_settings()
    if s.mode != "live":
        return None
    if s.llm_api_key:
        return "api"
    return "cli" if shutil.which("claude") else None


async def _ask_api(user_content: str) -> GuideOut | None:
    client = anthropic.AsyncAnthropic(api_key=get_settings().llm_api_key)
    response = await client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": user_content}],
        output_format=GuideOut,
    )
    if response.stop_reason == "refusal":
        return None
    return response.parsed_output


async def _ask_cli(user_content: str) -> GuideOut | None:
    """Headless Claude Code: `claude -p`, run in an empty temp dir so it has no project to touch."""
    schema = json.dumps(GuideOut.model_json_schema())
    prompt = (
        f"{SYSTEM}\n\n{user_content}\n\n"
        f"Reply with ONLY one JSON object matching this JSON Schema, no prose, no code fences:\n{schema}"
    )
    with tempfile.TemporaryDirectory() as cwd:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt, "--output-format", "json",
            cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), CLI_TIMEOUT_S)
        except TimeoutError:
            proc.kill()
            raise GuideUnavailable("Claude took too long; try again.") from None
    try:
        text = json.loads(stdout)["result"]
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return GuideOut.model_validate_json(match.group(0)) if match else None
    except (ValueError, KeyError, TypeError):
        return None


def _repo_files_query(owner: str, name: str) -> tuple[str, dict[str, str]]:
    fields, aliases = [], {}
    for kind, paths in FILES.items():
        for i, path in enumerate(paths):
            alias = f"{kind}_{i}"
            aliases[alias] = path
            fields.append(f'{alias}: object(expression: "HEAD:{path}") {{ ... on Blob {{ text }} }}')
    workflows = 'workflows: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name object { ... on Blob { text } } } } }'
    query = (
        "query RepoRules {\n"
        f"  repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{\n"
        "    nameWithOwner defaultBranchRef { name }\n    " + "\n    ".join(fields) + f"\n    {workflows}\n  }}\n}}"
    )
    return query, aliases


async def read_repo_rules(github: GitHub, repo: str) -> dict[str, str]:
    """{file path: text} for the rule files this repo has."""
    owner, name = repo.split("/", 1)
    query, aliases = _repo_files_query(owner, name)
    data = (await github.graphql(query, ttl=get_settings().ttl_repo_stats)).get("repository") or {}
    found: dict[str, str] = {}
    for alias, path in aliases.items():
        kind = alias.rsplit("_", 1)[0]
        blob = data.get(alias)
        if blob and blob.get("text") and not any(p in found for p in FILES[kind]):
            found[path] = blob["text"][:MAX_FILE_CHARS]
    for entry in ((data.get("workflows") or {}).get("entries") or [])[:2]:
        text = (entry.get("object") or {}).get("text")
        if text:
            found[f".github/workflows/{entry['name']}"] = text[:MAX_FILE_CHARS]
    return found


async def repo_facts(repo: str) -> list[dict]:
    rows = await _rows(
        "MATCH (:Repo {name: $repo})-[:HAS_FACT]->(f:RepoFact) RETURN f.text, f.source ORDER BY f.at",
        {"repo": repo},
    )
    return [{"fact": t, "source": s} for t, s in rows]


async def _save_repo_facts(repo: str, facts: list[Fact]) -> None:
    now = int(datetime.now(UTC).timestamp())
    for f in facts:
        fid = hashlib.sha1(f"{repo}:{f.fact.lower()}".encode()).hexdigest()[:12]
        await _rows(
            """
            MERGE (r:Repo {name: $repo})
            MERGE (f:RepoFact {id: $id})
            ON CREATE SET f.text = $text, f.source = $source, f.at = $now
            MERGE (r)-[:HAS_FACT]->(f)
            """,
            {"repo": repo, "id": fid, "text": f.fact, "source": f.source, "now": now},
        )


async def _save_guide(attempt_id: str, guide: dict) -> None:
    await _rows(
        "MATCH (a:Attempt {id: $aid}) SET a.guide = $guide, a.guide_at = $now",
        {"aid": attempt_id, "guide": json.dumps(guide), "now": int(datetime.now(UTC).timestamp())},
    )


async def saved_guide(attempt_id: str) -> dict | None:
    rows = await _rows("MATCH (a:Attempt {id: $aid}) RETURN a.guide", {"aid": attempt_id})
    return json.loads(rows[0][0]) if rows and rows[0][0] else None


SYSTEM = """You are the Guide in Breadcrumbs, an assistant that helps people land open-source contributions.
The user has picked a GitHub issue. Write the drafts they need to claim it, set up, and open the PR.

Rules:
- Follow the repository's own rules exactly. Use its real commands from package.json scripts, the Makefile, pyproject or CI, never generic guesses. If a rule file doesn't say, prefer what CI runs.
- If the repo has a PR template, fill in its sections. Include "Fixes #<number>".
- Personalise using the user's profile and memories: their level, their skills, the time they have. A beginner gets more explanation; an experienced contributor gets terse steps.
- Use what was already learned about this repo, and correct it if the files now say otherwise.
- Never invent rules the files don't contain. If something is unknown, leave it out.
- learned_about_repo: only durable facts a future contributor would need (package manager, test command, PR title convention, CLA, branch rules). Cite the file.
- learned_about_user: only durable facts about the user that would change future advice. Usually empty."""


async def write_guide(github: GitHub, login: str, issue_id: str) -> dict:
    how = provider()
    if how is None:
        raise GuideUnavailable("Set MODE=live and either LLM_API_KEY or install the Claude Code CLI to let the Guide agent write drafts.")

    owner, name, number = parse_issue_id(issue_id)
    repo = f"{owner}/{name}"
    aid = progress.attempt_id(login, issue_id)
    attempt = await progress.get_attempt(aid)
    if not attempt:
        raise KeyError(issue_id)
    fp = await progress.get_user(login)

    # The trace: every step the agent takes, shown in the UI like "See the query".
    trace: list[dict] = [
        {"step": "Read your profile from the graph", "detail": f"{fp.level} · {len(fp.skills)} skills · {fp.preferences.hours_per_week}h/week",
         "query": "MATCH (u:User {login: $login})-[k:KNOWS]->(t:Tech) RETURN u, k, t"},
    ]
    remembered = await memory.memories(login)
    trace.append({"step": "Recalled what it remembers about you", "detail": f"{len(remembered)} notes",
                  "query": "MATCH (:User {login: $login})-[:REMEMBERS]->(m:Memory) RETURN m"})
    known = await repo_facts(repo)
    trace.append({"step": f"Recalled what Breadcrumbs already learned about {repo}", "detail": f"{len(known)} facts",
                  "query": "MATCH (:Repo {name: $repo})-[:HAS_FACT]->(f:RepoFact) RETURN f"})
    try:
        files = await read_repo_rules(github, repo)
    except GitHubError:
        files = {}
    trace.append({"step": "Read the repo's own rules on GitHub", "detail": ", ".join(files) or "no rule files found", "query": None})
    issue_rows = await _rows("MATCH (i:Issue {id: $id}) RETURN i.title, i.difficulty", {"id": issue_id})

    context = {
        "issue": {"id": issue_id, "number": number, "title": attempt.issue_title, "url": attempt.issue_url,
                  "difficulty": issue_rows[0][1] if issue_rows else None},
        "user": {
            "login": fp.login, "level": fp.level, "merged_prs_elsewhere": fp.merged_prs,
            "skills": {sk.tech: round(sk.level * 100) for sk in fp.skills[:8]},
            "hours_per_week": fp.preferences.hours_per_week,
            "remembered": [m["text"] for m in remembered],
        },
        "already_learned_about_repo": known,
    }
    files_text = "\n\n".join(f"=== {path} ===\n{text}" for path, text in files.items()) or "(no rule files found)"

    user_content = f"Context from the user's graph:\n{json.dumps(context, indent=1)}\n\nThe repository's files:\n{files_text}"
    out = await (_ask_api(user_content) if how == "api" else _ask_cli(user_content))
    if out is None:
        raise GuideUnavailable("The Guide couldn't write drafts for this issue. Try again.")

    trace.append({"step": f"Wrote your drafts with Claude ({MODEL if how == 'api' else 'Claude Code CLI'})", "detail": "claim comment, setup steps, PR title and description", "query": None})

    out.learned_about_repo = out.learned_about_repo[:MAX_FACTS]  # show only what's saved
    out.learned_about_user = out.learned_about_user[:MAX_FACTS]
    await _save_repo_facts(repo, out.learned_about_repo)
    for f in out.learned_about_user[:MAX_FACTS]:
        await memory.remember(login, f.fact, "guide", f"guide:{issue_id}")
    trace.append({"step": "Saved what it learned to the graph",
                  "detail": f"{len(out.learned_about_repo[:MAX_FACTS])} repo facts, {len(out.learned_about_user[:MAX_FACTS])} notes about you",
                  "query": "MERGE (r:Repo {name: $repo})-[:HAS_FACT]->(f:RepoFact {text: $fact, source: $file})"})

    guide = out.model_dump() | {
        "sources": list(files),
        "used_repo_facts": len(known),
        "used_memories": len(remembered),
        "trace": trace,
        "at": datetime.now(UTC).isoformat(),
    }
    await _save_guide(aid, guide)
    return guide
