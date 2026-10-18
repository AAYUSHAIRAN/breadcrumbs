# Breadcrumbs

**Follow the trail from issue to merged PR.**

Enter your GitHub username. Get open-source issues you can actually get merged — from your first PR to your next one — plus a lit-up trail through the code to the fix.

See [breadcrumbs_design.md](breadcrumbs_design.md) for the feature and database design.

## Setup

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
cp .env.example .env     # MODE=mock works with no keys
make db                  # FalkorDB on :6379, browser UI on http://localhost:3002
make api                 # backend on http://localhost:8000 (API docs at /docs)
make web                 # frontend on http://localhost:3000
make test                # backend tests (needs `make db`)
```

```
backend/app/
├── config.py         MODE=mock|live, per-service fallback
├── github.py         live client (TTL cache + stale fallback) or fixtures
├── cache.py          Redis TTL cache
├── contracts.py      API models (mirrored in frontend/src/lib/contracts.ts)
├── fingerprint/      A1 skill fingerprint: one GraphQL call → skills + level
├── discovery/        B1/B3/B5: repo search → issues → checks (claims, repo stats) → ranked cards
├── registry.py       npm/PyPI package → GitHub repo (B3)
├── routes/           API endpoints
└── graph/
    ├── schema.py     indexes
    ├── progress.py   users, skills, attempts, events, skips
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

- **Live, not pre-loaded.** Issues, repos and PRs come from the GitHub API in real time. Search and API results are cached in Redis (the same FalkorDB instance) with a TTL. They are never written to the graph.
- **The graph stores progress.** It holds the user's journey (skills, attempts, a timeline of events, what they learned) and our progress with them (issues shown, skipped, selected), plus the code slice for each selected issue.
- **Progress happens on GitHub, too.** Users push commits and open PRs whenever they like. When they visit, we sync their active attempts from GitHub and append new events, deduplicated by GitHub IDs (commit SHA, PR number, review ID).
- **Good repos first, then their issues.** Searching issues directly mostly finds tiny personal repos whose owners label their own to-do lists "help wanted". So we search for mid-size, active repos (200–30k stars, pushed in the last 30 days, with labelled issues) in the user's top languages, add the repos behind their dependencies, then fetch those repos' issues in batched GraphQL calls.
- **Ranking is explainable arithmetic, not an LLM.** Fit = 0.35 skill + 0.20 difficulty (aimed one step above the user's level) + 0.20 maintainer speed + 0.15 newcomer merges + 0.10 freshness, ×0.3 if claimed. Claims are detected from comment phrasing ("can I work on this?"), and expire after 21 days unless a maintainer said go ahead. Full formula in `backend/app/discovery/rank.py`.
- **"Newcomers", not "first-timers".** GitHub reports an author's *current* relationship to a repo, so a merged first-timer shows as CONTRIBUTOR. We count merged PRs by people who aren't bots or maintainers and appear once in the repo's 50 most recent PRs.
- **No cloning.** Code comes from the Git Trees API plus raw file fetches, starting at the files the issue points to and following imports 1–2 levels out (~30–80 files). Cached by commit SHA.
- **No OAuth for the hackathon.** We use our own GitHub token, and the user posts the comments we draft for them.
- **Mock mode by default.** `MODE=mock` runs offline with fixtures for GitHub and the LLM. `MODE=live` uses real APIs, and a missing key falls back to mock for that service only.

### Progress model

```
(User)─KNOWS {level, source}─▶(Tech)
(User)─WORKING_ON─▶(Attempt {status, started_at, last_activity_at})─FOR─▶(Issue)─IN─▶(Repo)
(Attempt)─HAS_EVENT─▶(Event {type, gh_id, at, ...})   append-only timeline
(User)─SKIPPED {reason, at}─▶(Issue)
(User)─LEARNED {at}─▶(Tech)
(File)─CONTAINS─▶(Function)─CALLS─▶(Function)─TESTED_BY─▶(Test)   code slice per issue
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
| T2.5 | Coach drafts: claim comment, setup commands, PR description, review explainer | C2, C6, E1, E3 | B | ⬜ |

### Phase 3: Progress over time
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T3.1 | Sync engine: commits, PRs, reviews, merges → events (deduplicated) → status changes | D1, D2, G3 | A | ⬜ |
| T3.2 | Merged → `LEARNED` + level up → next, harder issue | F1, F2 | A | ⬜ |
| T3.3 | Gone-quiet nudge (`last_activity_at`) | G1 | A | ⬜ |
| T3.4 | Dashboard: active attempts, nudges, journey timeline | F3, G1, G3 | B | ⬜ |

### Phase 4: Demo
| # | Task | Journeys | Owner | Status |
|---|---|---|---|---|
| T4.1 | Demo repo we control (live commit → PR → merge → sync), pre-warmed cache | D1, D2, F1 | Both | ⬜ |
| T4.2 | Pitch slides: growth chart, mentor match, maintainer view, company onboarding | F4, I1, I2, I4 | Both | ⬜ |
| T4.3 | Stretch: paste your own issue or repo URL | B4 | B | ⬜ |
| T4.4 | README, architecture diagram, backup video, 3 rehearsals | — | Both | ⬜ |

## User journey tracker

**Scope:** ✅ build · 🟡 stretch · 🖼️ pitch slide only · blank = cut
**Status:** ⬜ todo · 🔨 in progress · ✔️ done

**Priority:** P0 = demo depends on it · P1 = include if time allows · P2 = later

**Demo path:** A1 → B1 → B5 → C1 → C2 → C4 → C5 → C6 → D1/D2 → E1 → F1 → F2 → G3

**Totals:** 23 build (13 P0 + 8 P1 + 2 P2) · 1 stretch · 4 slides · 30 cut

| # | Journey | Pri | Scope | Status |
|---|---|---|---|---|
| **A. Onboarding** |||||
| A1 | New to open source, enters username → fingerprint → skill radar | P0 | ✅ | ⬜ |
| A2 | Already contributes → import past merged PRs, higher level | P1 | ✅ | ⬜ |
| A3 | Little or no public code → ask languages and level | P1 | | |
| A4 | Sign in with GitHub OAuth | P1 | | |
| A5 | Edit skills by hand | P2 | ✅ | ✔️ |
| A6 | Set goals (PRs per month, tech to learn) | P2 | | |
| **B. Discover** |||||
| B1 | Browse ranked issue cards with why-chips (live + cached) | P0 | ✅ | ✔️ |
| B2 | Filter by language, label, size, repo | P1 | | |
| B3 | "In my dependencies" 📦 | P1 | ✅ | ✔️ |
| B4 | Paste your own issue or repo URL | P1 | 🟡 | ⬜ |
| B5 | Inspect issue: why, claim status, maintainer speed, size | P0 | ✅ | ✔️ |
| B6 | Skip → hidden next time | P1 | ✅ | ✔️ |
| B7 | Save for later | P2 | ✅ | ✔️ |
| B8 | No good matches → widen search | P1 | | |
| B9 | Compare issues side by side | P2 | | |
| **C. Start an attempt** |||||
| C1 | Pick issue → new Attempt + `selected` event | P0 | ✅ | ⬜ |
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
| G7 | GitHub down or rate-limited → cached fallback | P1 | ✅ | ⬜ |
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
