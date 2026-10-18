import type {
  Attempt,
  Guide,
  GuideFact,
  Memory,
  Fingerprint,
  GraphView,
  IssueCard,
  IssueDetail,
  Matches,
  Preferences,
  SkipRequest,
} from "./contracts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `API error ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body.detail ?? body);
  }
  return resp.status === 204 ? (undefined as T) : resp.json();
}

const user = (login: string) => `/users/${encodeURIComponent(login)}`;

/** "owner/repo#123" → "owner/repo/123", the path form the API and our routes use. */
export const issuePath = (issueId: string) => issueId.replace("#", "/");

export const api = {
  fingerprint: (login: string) => request<Fingerprint>(`${user(login)}/fingerprint`),
  setPreferences: (login: string, prefs: Preferences) =>
    request<Fingerprint>(`${user(login)}/preferences`, { method: "PUT", body: JSON.stringify(prefs) }),
  matches: (login: string) => request<Matches>(`${user(login)}/matches`),
  issue: (login: string, issueId: string) => request<IssueDetail>(`${user(login)}/issues/${issuePath(issueId)}`),
  why: (login: string, issueId: string) => request<GraphView>(`${user(login)}/issues/${issuePath(issueId)}/why`),
  saved: (login: string) => request<IssueCard[]>(`${user(login)}/saved`),
  save: (login: string, card: IssueCard) =>
    request<void>(`${user(login)}/saved`, { method: "POST", body: JSON.stringify(card) }),
  unsave: (login: string, issueId: string) =>
    request<void>(`${user(login)}/saved/${issuePath(issueId)}`, { method: "DELETE" }),
  skip: (login: string, issueId: string, reason: SkipRequest["reason"]) =>
    request<void>(`${user(login)}/issues/${issuePath(issueId)}/skip`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  attempts: (login: string) => request<Attempt[]>(`${user(login)}/attempts`),
  attempt: (login: string, issueId: string) => request<Attempt>(`${user(login)}/attempts/${issuePath(issueId)}`),
  pick: (login: string, issueId: string, force = false) =>
    request<Attempt>(`${user(login)}/attempts`, {
      method: "POST",
      body: JSON.stringify({ issue_id: issueId, force }),
    }),
  trailGraph: (login: string) => request<GraphView>(`${user(login)}/graph`),
  guide: (login: string, issueId: string) => request<Guide | Record<string, never>>(`${user(login)}/attempts/${issuePath(issueId)}/guide`),
  writeGuide: (login: string, issueId: string) =>
    request<Guide>(`${user(login)}/attempts/${issuePath(issueId)}/guide`, { method: "POST" }),
  memory: (login: string) => request<{ memories: Memory[] }>(`${user(login)}/memory`),
  forget: (login: string, id: string) => request<void>(`${user(login)}/memory/${id}`, { method: "DELETE" }),
  repoFacts: (login: string, repo: string) => request<GuideFact[]>(`${user(login)}/repo-facts/${repo}`),
};

/** The 409 body from POST /attempts when the issue was taken since it was shown. */
export interface Unavailable {
  issue_id: string;
  reason: "closed" | "assigned" | "pr_open" | "claimed" | "not_found";
  message: string;
  detail_url: string | null;
}

/** Parse "https://github.com/o/r/issues/12" or "o/r#12" into "o/r#12". */
export function parseIssueRef(input: string): string | null {
  const s = input.trim();
  const url = s.match(/github\.com\/([\w.-]+)\/([\w.-]+)\/issues\/(\d+)/);
  if (url) return `${url[1]}/${url[2]}#${url[3]}`;
  const short = s.match(/^([\w.-]+)\/([\w.-]+)#(\d+)$/);
  return short ? `${short[1]}/${short[2]}#${short[3]}` : null;
}
