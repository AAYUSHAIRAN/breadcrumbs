# Breadcrumbs

**Follow the trail from issue to merged PR.**

Enter your GitHub username. Get open-source issues you can actually get merged — from your first PR to your next one — plus a lit-up trail through the code to the fix.

See [breadcrumbs_design.md](breadcrumbs_design.md) for the feature and database design.

## Setup

_TBD_

## User journey tracker

**Scope:** ✅ build · 🟡 stretch · 🖼️ pitch slide only · blank = cut
**Status:** ⬜ todo · 🔨 in progress · ✔️ done

**Priority:** P0 = demo depends on it · P1 = include if time allows · P2 = later

**Demo path:** A1 → B1 → B5 → C1 → C2 → C4 → C5 → C6 → D1/D2 → E1 → F1 → F2 → G3

**Totals:** 21 build (13 P0 + 8 P1) · 1 stretch · 4 slides · 32 cut

| # | Journey | Pri | Scope | Status |
|---|---|---|---|---|
| **A. Onboarding** |||||
| A1 | New to open source, enters username → fingerprint → skill radar | P0 | ✅ | ⬜ |
| A2 | Already contributes → import past merged PRs, higher level | P1 | ✅ | ⬜ |
| A3 | Little or no public code → ask languages and level | P1 | | |
| A4 | Sign in with GitHub OAuth | P1 | | |
| A5 | Edit skills by hand | P2 | | |
| A6 | Set goals (PRs per month, tech to learn) | P2 | | |
| **B. Discover** |||||
| B1 | Browse ranked issue cards with why-chips (live + cached) | P0 | ✅ | ⬜ |
| B2 | Filter by language, label, size, repo | P1 | | |
| B3 | "In my dependencies" 📦 | P1 | ✅ | ⬜ |
| B4 | Paste your own issue or repo URL | P1 | 🟡 | ⬜ |
| B5 | Inspect issue: why, claim status, maintainer speed, size | P0 | ✅ | ⬜ |
| B6 | Skip → hidden next time | P1 | ✅ | ⬜ |
| B7 | Save for later | P2 | | |
| B8 | No good matches → widen search | P1 | | |
| B9 | Compare issues side by side | P2 | | |
| **C. Start an attempt** |||||
| C1 | Pick issue → new Attempt + `selected` event | P0 | ✅ | ⬜ |
| C2 | Draft claim comment from CONTRIBUTING.md | P0 | ✅ | ⬜ |
| C3 | Claimed in the meantime → recheck, warn, next best | P1 | ✅ | ⬜ |
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
| F3 | Journey timeline | P1 | ✅ | ⬜ |
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
