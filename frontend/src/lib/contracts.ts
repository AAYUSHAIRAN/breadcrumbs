// API contracts. Mirror of backend/app/contracts.py — keep the two in sync.
// Issue IDs are "owner/repo#number" everywhere.

export type Level = "beginner" | "intermediate" | "advanced";
export type Difficulty = "easy" | "medium" | "hard";

export type AttemptStatus =
  | "selected"
  | "in_progress"
  | "pr_open"
  | "in_review"
  | "changes_requested"
  | "merged"
  | "closed"
  | "abandoned";

export type EventType =
  | "selected"
  | "commit"
  | "pr_opened"
  | "review_commented"
  | "changes_requested"
  | "approved"
  | "merged"
  | "pr_closed"
  | "issue_closed"
  | "abandoned";

// --- Onboarding --------------------------------------------------------------

export interface Skill {
  tech: string;
  kind: "language" | "framework" | "library" | "tool";
  level: number; // 0–1
  source: "inferred" | "manual" | "learned";
}

export interface Preferences {
  languages: string[]; // empty = use the user's strongest languages
  difficulty: "auto" | "easy" | "medium" | "hard"; // auto = one step above their level
  hours_per_week: number;
}

export interface Fingerprint {
  login: string;
  name: string | null;
  avatar_url: string | null;
  level: Level;
  skills: Skill[];
  merged_prs: number;
  dependencies: string[]; // packages from dependency files, e.g. "npm:react", "pypi:fastapi"
  preferences: Preferences;
}

// --- Discovery ---------------------------------------------------------------

export interface WhyChip {
  kind:
    | "skill"
    | "unclaimed"
    | "fast_maintainer"
    | "newcomers"
    | "small_scope"
    | "dependency"
    | "warning";
  label: string;
}

export interface IssueCard {
  id: string;
  url: string;
  repo: string;
  number: number;
  title: string;
  labels: string[];
  updated_at: string;
  difficulty: Difficulty;
  fit: number;
  merge_forecast: number;
  claimed: boolean;
  maintainer_reply_hours: number | null;
  newcomer_merges_90d: number; // merged PRs by non-bot, non-maintainer authors seen once in recent PRs
  repo_stars: number;
  in_dependencies: boolean;
  tech: string; // the skill this issue draws on
  breakdown: Record<"skill" | "difficulty" | "maintainer" | "newcomers" | "freshness", number>;
  saved: boolean;
  why: WhyChip[];
}

export interface Matches {
  login: string;
  issues: IssueCard[]; // this page, or everything when not paged (page_size 0)
  total: number;
  page: number;
  page_size: number;
  stale: boolean;
}

export interface RepoHealth {
  repo: string;
  stars: number;
  reply_hours: number | null;
  newcomer_merges_90d: number;
  newcomer_merged: number;
  newcomer_closed: number;
}

export interface IssueDetail {
  card: IssueCard;
  body: string; // markdown
  comments: number;
  claimed_by: string | null;
  repo: RepoHealth;
  attempt_id: string | null;
  stale: boolean;
}

export interface SkipRequest {
  reason: "not_interested" | "too_hard" | "too_easy" | "wrong_tech" | "other";
}

// --- Attempts and progress ---------------------------------------------------

export interface Event {
  type: EventType;
  at: string;
  gh_id: string | null;
  url: string | null;
  summary: string;
}

export interface Attempt {
  id: string;
  issue_id: string;
  issue_title: string;
  issue_url: string;
  status: AttemptStatus;
  started_at: string;
  last_activity_at: string;
  pr_url: string | null;
  events: Event[];
}

export interface Nudge {
  attempt_id: string;
  kind: "quiet" | "review_waiting" | "changes_requested";
  message: string;
}

export interface Dashboard {
  user: Fingerprint;
  active: Attempt[];
  finished: Attempt[];
  nudges: Nudge[];
  stale: boolean;
}

// --- Guidance ----------------------------------------------------------------

export interface ReadingStep {
  order: number;
  file: string;
  symbol: string | null;
  role: "entry" | "step" | "target" | "test";
  url: string;
  why: string;
}

export interface CodeNode {
  id: string;
  kind: "file" | "function" | "class" | "test";
  label: string;
}

export interface CodeEdge {
  source: string;
  target: string;
  kind: "contains" | "calls" | "imports" | "tested_by";
}

export interface ReadingPath {
  issue_id: string;
  commit_sha: string;
  steps: ReadingStep[];
  nodes: CodeNode[];
  edges: CodeEdge[];
}

export interface Precedent {
  pr_url: string;
  title: string;
  author: string;
  first_time: boolean;
  reviewer: string | null;
  reply_hours: number | null;
  merged_at: string;
  shared_files: string[];
}

export interface Draft {
  kind: "claim_comment" | "setup" | "pr_description" | "review_explainer";
  text: string;
  sources: string[];
}

// --- Graph views -------------------------------------------------------------------

export interface GraphNode {
  id: string;
  kind: "user" | "tech" | "issue" | "repo" | "fact";
  label: string;
  detail: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface GraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  cypher: string;
}

// --- Guide agent -----------------------------------------------------------------

export interface GuideTraceStep {
  step: string;
  detail: string;
  query: string | null;
}

export interface GuideFact {
  fact: string;
  source: string;
}

export interface Guide {
  claim_comment: string;
  setup_steps: { command: string; why: string }[];
  pr_title: string;
  pr_description: string;
  tips: string[];
  learned_about_repo: GuideFact[];
  learned_about_user: GuideFact[];
  sources: string[];
  used_repo_facts: number;
  used_memories: number;
  trace: GuideTraceStep[];
  at: string;
}

export interface Memory {
  id: string;
  text: string;
  kind: string;
  at: number;
}
