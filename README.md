# Breadcrumbs

**Follow the trail from issue to merged PR.**

Enter your GitHub username. Get open-source issues you can actually get merged, from your first PR to your next one, and follow your progress over time.

> [breadcrumbs_design.md](breadcrumbs_design.md) is the original plan. Where they differ, the **Decisions** below win: we moved from pre-loading repos to live GitHub data, and from cloning to fetching only the code we need.

## What works today

- **Onboarding:** enter a username → skills read from public repos, dependency files and merged PRs → choose search languages, difficulty and hours per week.
- **Discover:** ranked issues from active repos in your languages and dependencies, with why-chips, fit and merge-chance scores, a score breakdown, filters, save, skip (with undo) and keyboard shortcuts. Paste any GitHub issue URL to score it.
- **Issue page:** the issue's text, how the repo treats newcomers, and the graph path from you to the issue, with the Cypher that produced it.
- **Picking an issue:** re-checked against live GitHub first (assigned? PR open? claimed in a comment?), then it opens a workspace with a progress stepper, next step, a guide (claim comment, setup commands, PR template) and a timeline.
- **Home, My trail, Profile:** what you're working on, your attempts by status, and your trail as a graph.

**Not built yet:** syncing your commits and PRs from GitHub (the stepper only moves when that lands), the code map, past PRs, LLM-written drafts, and level-ups after a merge. See [Tasks](#tasks).

## Setup

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
cp .env.example .env     # set MODE=live and GITHUB_TOKEN for real data (see below)
make db                  # FalkorDB on :6379, browser UI on http://localhost:3002
make api                 # backend on http://localhost:8000 (API docs at /docs)
make web                 # frontend on http://localhost:3000
make test                # backend tests (needs `make db`)
make lint                # ruff + eslint
```

**Live mode** (`MODE=live`) needs `GITHUB_TOKEN`: a classic personal access token with no scopes is enough, since we only read public data. Without a token, live mode falls back to mock.

**Mock mode** (`MODE=mock`, the default) serves GitHub responses recorded from one real account (`AAYUSHAIRAN`) in `backend/fixtures/github/`, so it runs offline. Any username returns that same recorded data, and because matches drop issues not updated in 60 days, mock results thin out as the recordings age. The tests pin the date, so they don't.

The frontend calls the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). There's no sign-in: the app remembers your username in the browser.

```
backend/app/
├── config.py         MODE=mock|live, per-service fallback
├── github.py         live client (TTL cache + stale fallback) or recorded fixtures
├── cache.py          Redis TTL cache
├── contracts.py      API models (mirrored in frontend/src/lib/contracts.ts)
├── fingerprint/      A1 skill fingerprint: one GraphQL call → skills + level
├── discovery/        repo search → issues → checks (claims, repo stats) → ranked cards; single-issue detail
├── registry.py       npm/PyPI package → GitHub repo (B3)
├── routes/           API endpoints
└── graph/
    ├── schema.py     indexes
    ├── progress.py   users, skills, preferences, attempts, events, shown / saved / skipped issues
    ├── status.py     attempt status machine
    └── views.py      graph views for the UI ("why this match", "your trail"), each with its Cypher

frontend/src/
├── app/              routes: / (landing), /start (onboarding), and the app: /home, /discover,
│                     /issues/[owner]/[repo]/[number], /trail, /trail/[owner]/[repo]/[number], /profile
├── components/
│   ├── screens/      one component per screen
│   ├── graph/        GraphView: deterministic SVG graph with "see the query"
│   ├── issues/       issue rows, summary panel, score breakdown, actions (pick, save, skip with undo)
│   ├── attempts/     stepper, timeline, next-step rules
│   └── shell/        sidebar app frame
└── lib/              API client, SWR hooks, session (remembered username), contracts
```

## Decisions

- **Live, not pre-loaded.** Issues, repos and PRs come from the GitHub API in real time. API results are cached in Redis (the same FalkorDB instance) with a TTL: 15 minutes for searches, 24 hours for repo stats. Each cache entry also keeps a 7-day stale copy, served if GitHub is down or rate-limited (the UI says so).
- **The graph stores progress, not GitHub.** Candidate issues are never bulk-loaded. The graph holds the user's journey (skills, preferences, attempts, a timeline of events, what they learned) and our side of it: the issues we showed them, with the skill each one needs and its repo's stats, plus the ones they saved or skipped. That's what makes the "why this match" and "your trail" views real Cypher traversals.
- **Good repos first, then their issues.** Searching issues directly mostly finds tiny personal repos whose owners label their own to-do lists "help wanted". So we search for mid-size, active repos (200–30k stars, pushed in the last 30 days, with labelled issues) in the user's top or chosen languages, add the repos behind their dependencies, then fetch those repos' issues in batched GraphQL calls.
- **Ranking is explainable arithmetic, not an LLM.** Fit = 0.35 skill + 0.20 difficulty (aimed one step above the user's level, or their chosen difficulty) + 0.20 maintainer speed + 0.15 newcomer merges + 0.10 freshness, +0.05 for a dependency, ×0.3 if claimed. Claims are detected from comment phrasing ("can I work on this?"), and expire after 21 days unless a maintainer said go ahead. Full formula in `backend/app/discovery/rank.py`; the UI shows the breakdown.
- **"Newcomers", not "first-timers".** GitHub reports an author's *current* relationship to a repo, so a merged first-timer shows as CONTRIBUTOR. We count merged PRs by people who aren't bots or maintainers and appear once in the repo's 50 most recent PRs.
- **Re-check before picking.** Matches can be 15 minutes old, so picking an issue re-fetches it live (bypassing the cache) and refuses with the reason if it was assigned, got a PR or was claimed meanwhile. The user can take it anyway.
- **Planned: progress syncs from GitHub.** Users push commits and open PRs whenever they like. When they visit, we'll sync their active attempts from GitHub and append new events, deduplicated by GitHub IDs (commit SHA, PR number, review ID). *(T3.1)*
- **Planned: no cloning.** Code will come from the Git Trees API plus raw file fetches, starting at the files the issue points to and following imports 1–2 levels out (~30–80 files), cached by commit SHA. *(T2.2)*
- **No OAuth for the hackathon.** We use our own GitHub token, and the user posts the comments we draft for them.
- **Mock mode by default,** with a per-service fallback: in live mode, a missing key drops only that service back to mock. No LLM is used yet; drafts in the Guide tab are templates.

### Graph model

```
(User {login, level, pref_*})─KNOWS {level, source}─▶(Tech)
(User)─WORKING_ON─▶(Attempt {status, started_at, last_activity_at})─FOR─▶(Issue)─IN─▶(Repo)
(Attempt)─HAS_EVENT─▶(Event {type, gh_id, at, ...})        append-only timeline
(User)─SHOWN {fit, at, times}─▶(Issue)─NEEDS─▶(Tech)        what we recommended, and why
(Repo {stars, reply_hours, newcomer_merges_90d})
(User)─SAVED {card, at}─▶(Issue)    (User)─SKIPPED {reason, at}─▶(Issue)
(User)─LEARNED {at}─▶(Tech)
planned: (File)─CONTAINS─▶(Function)─CALLS─▶(Function)─TESTED_BY─▶(Test)   code slice per issue
```

Attempt status: `selected → in_progress → pr_open → in_review ⇄ changes_requested → merged`, or `closed` / `abandoned`

## Tasks

**Status:** ⬜ todo · 🔨 in progress · ✔️ done · **Owner:** A = data + graph · B = agent + UI

### Phase 0: Foundation
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T0.1 | Scaffold: `backend/` (FastAPI, uv), `frontend/` (Next.js + TS + Tailwind), `docker-compose.yml` (FalkorDB), `.env.example`, `Makefile` | — | A | ✔️ |
| T0.2 | Config + mock/live switch; GitHub client with Redis TTL cache and rate-limit handling | G7 | A | ✔️ |
| T0.3 | Shared contracts: Pydantic models + matching TypeScript types for the API | — | B | ✔️ |
| T0.4 | Graph schema, indexes, and a progress repository (User, Tech, Attempt, Event, …) | — | A | ✔️ |
| T0.5 | Test the planned Cypher against FalkorDB (progress queries done; code-slice queries come with T2.2) | — | A | 🔨 |

### Phase 1: Onboard and discover
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T1.1 | Fingerprint: repos, languages, dependency files → `KNOWS {level}` | A1 | A | ✔️ |
| T1.2 | Import past merged PRs as completed attempts → starting level | A2 | A | ⬜ |
| T1.3 | Issue search: repo search per top language (mid-size, active, with labelled issues) + dependency repos, then batched GraphQL for their open issues; drop assigned, PR-linked, stale and seen issues | B1, B3 | A | ✔️ |
| T1.4 | Check each candidate (claims from comments, maintainer reply time, newcomer merges) → rank → why-chips and merge forecast; remember what we showed (`SHOWN`) | B1, B5 | B | ✔️ |
| T1.5 | Skip (`SKIPPED`), and recheck the claim at pick time | B6, C3 | A | ✔️ |
| T1.6 | UI: landing, skill bars, issue cards (why-chips, fit and merge-chance meters, details), pick and skip, your trail | A1, B1, B5 | B | ✔️ |

### Phase UI: Product UI and graph visuals
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| U1 | App shell: sidebar nav (Home, Discover, My trail, Profile), remembered user, toasts, skeletons, empty states, mobile | — | B | ✔️ |
| U2 | Onboarding `/start`: username → "reading your GitHub" → profile reveal, confirm search languages, difficulty, hours per week | A1, A5 | B | ✔️ |
| U3 | Discover (filters, list + detail panel, keyboard) and Issue page (rendered issue, score breakdown, repo health); save for later | B1–B7 | B | ✔️ |
| U4 | "Why this match" graph: write issue → tech/repo into the graph, draw the real Cypher path, "see the query" toggle | B5 | A + B | ✔️ |
| U5 | Workspace per attempt: progress stepper, next-step card, tabs (Guide and Timeline work; Code map and Past PRs fill in with T2.2–T2.4) | C1–C6, D, E | B | ✔️ |
| U6 | Home dashboard, My trail, Profile with skill bars and "your trail" graph (attempts → repos → skills learned) | F3, G3 | A + B | ✔️ |

### Phase 2: Attempt and guidance
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T2.1 | Pick an issue → Attempt + `selected` event | C1 | A | ✔️ |
| T2.2 | Code slice: Trees API + raw files + tree-sitter + follow imports → Layer 2, cached by SHA | C4 | A | ⬜ |
| T2.3 | Reading path query + code map UI that lights up step by step | C4 | B | ⬜ |
| T2.4 | Past PRs that touched the same files | C5 | A | ⬜ |
| T2.5 | Coach drafts from the repo's own CONTRIBUTING.md and CI config (LLM): claim comment, setup commands, PR description, review explainer. Generic templates are in the Guide tab today | C2, C6, E1, E3 | B | ⬜ |

### Phase 3: Progress over time
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T3.1 | Sync engine: commits, PRs, reviews, merges → events (deduplicated) → status changes | D1, D2, G3 | A | ⬜ |
| T3.2 | Merged → `LEARNED` + level up → next, harder issue | F1, F2 | A | ⬜ |
| T3.3 | Gone-quiet nudge (`last_activity_at`) | G1 | A | ⬜ |
| T3.4 | Nudges on Home (gone quiet, review waiting); timeline events from sync | G1, G3 | B | ⬜ |

### Phase 4: Demo
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T4.1 | Demo repo we control (live commit → PR → merge → sync), pre-warmed cache | D1, D2, F1 | Both | ⬜ |
| T4.2 | Pitch slides: growth chart, mentor match, maintainer view, company onboarding | F4, I1, I2, I4 | Both | ⬜ |
| T4.3 | Stretch: paste your own issue URL (done via the Issue page); repo URLs not yet | B4 | B | ✔️ |
| T4.4 | README, architecture diagram, backup video, 3 rehearsals | — | Both | ⬜ |

## User journey tracker

**Scope:** ✅ build · 🟡 stretch · 🖼️ pitch slide only · blank = cut
**Status:** ⬜ todo · 🔨 in progress · ✔️ done

**Priority:** P0 = demo depends on it · P1 = include if time allows · P2 = later

**Demo path:** A1 → B1 → B5 → C1 → C2 → C4 → C5 → C6 → D1/D2 → E1 → F1 → F2 → G3

**Totals:** 24 build (14 P0 + 8 P1 + 2 P2) · 1 stretch · 4 slides · 29 cut

**Done:** 11 of 24 build journeys (A1, A5, B1, B3, B5, B6, B7, C1, C3, F3, G7), plus the B4 stretch

| # | Journey | Pri | Scope | Status |
|---|---|---|---|---|
| **A. Onboarding** |||||
| A1 | New to open source, enters username → fingerprint → skills | P0 | ✅ | ✔️ |
| A2 | Already contributes → import past merged PRs, higher level | P1 | ✅ | ⬜ |
| A3 | Little or no public code → ask languages and level | P1 | | |
| A4 | Sign in with GitHub OAuth | P1 | | |
| A5 | Adjust what we search for: languages, difficulty, hours per week (instead of editing skills) | P2 | ✅ | ✔️ |
| A6 | Set goals (PRs per month, tech to learn) | P2 | | |
| **B. Discover** |||||
| B1 | Browse ranked issue cards with why-chips (live + cached) | P0 | ✅ | ✔️ |
| B2 | Filter by language, label, size, repo | P1 | | |
| B3 | "In my dependencies" 📦 | P1 | ✅ | ✔️ |
| B4 | Paste your own issue URL (repo URLs not yet) | P1 | 🟡 | ✔️ |
| B5 | Inspect issue: why, claim status, maintainer speed, size | P0 | ✅ | ✔️ |
| B6 | Skip → hidden next time | P1 | ✅ | ✔️ |
| B7 | Save for later | P2 | ✅ | ✔️ |
| B8 | No good matches → widen search | P1 | | |
| B9 | Compare issues side by side | P2 | | |
| **C. Start an attempt** |||||
| C1 | Pick issue → new Attempt + `selected` event | P0 | ✅ | ✔️ |
| C2 | Draft claim comment from CONTRIBUTING.md | P0 | ✅ | ⬜ |
| C3 | Claimed in the meantime → recheck, warn, next best | P1 | ✅ | ✔️ |
| C4 | Code map: lit-up path entry → target → test | P0 | ✅ | ⬜ |
| C5 | Past PRs that touched the same files | P0 | ✅ | ⬜ |
| C6 | Local setup commands from README, CONTRIBUTING, CI | P0 | ✅ | ⬜ |
| C7 | Ask about the code (coach with citations) | P1 | | |
| C8 | Maintainer assigns or declines → status updated | P1 | | |
| C9 | Several attempts at once | P2 | | |
| **D. Work away from Breadcrumbs** |||||
| D1 | Pushes commits → sync → `commit` events | P0 | ✅ | ⬜ |
| D2 | Opens PR directly on GitHub → sync detects it | P0 | ✅ | ⬜ |
| D3 | Stuck → coach helps | P1 | | |
| D4 | CI fails → coach explains | P1 | | |
| D5 | Merge conflict → rebase steps | P2 | | |
| D6 | Unexpected branch or fork → match via `closes #N` | P1 | | |
| **E. Review** |||||
| E1 | Draft PR description | P0 | ✅ | ⬜ |
| E2 | Waiting on review → expected wait, nudge | P1 | | |
| E3 | Changes requested → coach explains the review | P1 | ✅ | ⬜ |
| E4 | Pushes fixes → back to in_review (repeats) | P1 | | |
| E5 | PR closed unmerged → no penalty, similar issue | P1 | | |
| E6 | Issue closed by someone else or duplicate | P1 | | |
| E7 | Draft reply to the reviewer | P2 | | |
| **F. Merge and grow** |||||
| F1 | Merged 🎉 → LEARNED → level up | P0 | ✅ | ⬜ |
| F2 | Next, harder issue (growth ladder) | P0 | ✅ | ⬜ |
| F3 | Journey timeline | P1 | ✅ | ✔️ |
| F4 | Growth stats chart | P1 | 🖼️ | ⬜ |
| F5 | Shareable profile or badge | P2 | | |
| F6 | Regular in one repo → medium or core issues | P2 | | |
| **G. Coming back, going quiet, edge cases** |||||
| G1 | Quiet for N days → "still on it?" nudge | P1 | ✅ | ⬜ |
| G2 | Abandon → unclaim comment, record why | P1 | | |
| G3 | Returns after weeks → sync catches up | P0 | ✅ | ⬜ |
| G4 | Background sync job | P1 | | |
| G5 | Notifications (email or in-app) | P2 | | |
| G6 | Repo archived or issue locked → close automatically | P2 | | |
| G7 | GitHub down or rate-limited → cached fallback | P1 | ✅ | ✔️ |
| **H. Account and privacy** |||||
| H1 | View stored data | P2 | | |
| H2 | Delete account and data | P2 | | |
| H3 | Disconnect GitHub | P2 | | |
| H4 | Viewing someone else's username → read-only | P1 | | |
| **I. Other sides** |||||
| I1 | Mentor match | P2 | 🖼️ | ⬜ |
| I2 | Maintainer view | P2 | 🖼️ | ⬜ |
| I3 | Maintainer marks issues Breadcrumbs-friendly | P2 | | |
| I4 | Company onboarding on an internal repo | P2 | 🖼️ | ⬜ |
| I5 | Cohort or bootcamp leaderboard | P2 | | |
